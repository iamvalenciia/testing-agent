"""Guardrails Service for Model Drift and Hallucination Detection.

This module provides validators to detect when the agent deviates from
expected behavior patterns (drift) or takes unnecessary actions (hallucinations).

Components:
- StepCountValidator: Compare actual steps vs reference workflow
- ActionSequenceValidator: Detect out-of-order or unexpected actions
- ContextRelevanceScorer: Score whether loaded context was actually used
- GuardrailService: Orchestrates all validators and collects metrics
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class DriftType(str, Enum):
    """Types of drift that can be detected."""
    NONE = "none"
    EXTRA_STEPS = "extra_steps"
    MISSING_STEPS = "missing_steps"
    SEQUENCE_MISMATCH = "sequence_mismatch"
    CONTEXT_POLLUTION = "context_pollution"
    ADAPTIVE_RECOVERY = "adaptive_recovery"  # Not really drift - intelligent behavior


@dataclass
class ValidationResult:
    """Result from a guardrail validator."""
    valid: bool
    drift_type: DriftType = DriftType.NONE
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailContext:
    """Holds reference workflow data and actual execution data for comparison.
    
    This is populated during agent execution and passed to validators
    after task completion.
    """
    # Reference data (from Pinecone workflow)
    reference_step_count: Optional[int] = None
    reference_actions: Dict[str, int] = field(default_factory=dict)  # action_type -> count
    reference_urls: List[str] = field(default_factory=list)
    reference_final_url: Optional[str] = None
    
    # Actual execution data
    actual_step_count: int = 0
    actual_actions: Dict[str, int] = field(default_factory=dict)
    actual_urls: List[str] = field(default_factory=list)
    actual_final_url: Optional[str] = None
    actual_steps: List[Dict] = field(default_factory=list)  # Full step details
    
    # Context loading tracking
    static_data_loaded: bool = False
    static_data_content: List[str] = field(default_factory=list)
    static_data_referenced_in_reasoning: bool = False
    
    # Outcome
    task_completed_successfully: bool = False


class StepCountValidator:
    """Compare actual step count vs reference workflow.
    
    Detects when the agent uses more or fewer steps than expected.
    Allows for ±1 step variance as acceptable tolerance.
    """
    
    ACCEPTABLE_VARIANCE = 1  # Allow 1 extra or missing step
    
    def validate(self, ctx: GuardrailContext) -> ValidationResult:
        """
        Validate step count against reference.
        
        Returns:
            ValidationResult with details about step count comparison
        """
        if ctx.reference_step_count is None:
            # No reference available - can't validate
            return ValidationResult(
                valid=True,
                message="No reference workflow - step count validation skipped"
            )
        
        diff = ctx.actual_step_count - ctx.reference_step_count
        
        details = {
            "expected_steps": ctx.reference_step_count,
            "actual_steps": ctx.actual_step_count,
            "difference": diff,
        }
        
        if abs(diff) <= self.ACCEPTABLE_VARIANCE:
            return ValidationResult(
                valid=True,
                message=f"Step count within tolerance: {ctx.actual_step_count}/{ctx.reference_step_count}",
                details=details
            )
        
        if diff > 0:
            # Extra steps taken
            extra_steps = ctx.actual_steps[ctx.reference_step_count:]
            extra_action_types = [s.get("action_type", "unknown") for s in extra_steps]
            details["extra_steps"] = extra_action_types
            
            # Check if this is adaptive recovery (extra steps but correct outcome)
            if ctx.task_completed_successfully:
                # Check if final URL matches expected
                url_matches = (
                    ctx.reference_final_url is None or 
                    ctx.actual_final_url == ctx.reference_final_url or
                    (ctx.reference_final_url and ctx.actual_final_url and 
                     ctx.reference_final_url.split("?")[0] == ctx.actual_final_url.split("?")[0])
                )
                
                if url_matches:
                    details["adaptive_recovery"] = True
                    return ValidationResult(
                        valid=True,  # Not blocking, just informational
                        drift_type=DriftType.ADAPTIVE_RECOVERY,
                        message=f"Adaptive recovery detected: {diff} extra steps taken but outcome correct",
                        details=details
                    )
            
            return ValidationResult(
                valid=False,
                drift_type=DriftType.EXTRA_STEPS,
                message=f"Drift detected: {diff} extra steps ({extra_action_types})",
                details=details
            )
        else:
            # Fewer steps (might indicate skipping)
            details["missing_steps"] = abs(diff)
            return ValidationResult(
                valid=True,  # Fewer steps is usually good (efficiency)
                message=f"Fewer steps than reference: {ctx.actual_step_count} vs {ctx.reference_step_count}",
                details=details
            )


class ActionSequenceValidator:
    """Detect out-of-order or unexpected actions.
    
    Compares the sequence of action types (ignoring coordinates/arguments)
    to detect when the agent invents new actions not in the reference.
    """
    
    def validate(self, ctx: GuardrailContext) -> ValidationResult:
        """
        Validate action sequence against reference.
        
        Returns:
            ValidationResult with details about action sequence comparison
        """
        if not ctx.reference_actions:
            return ValidationResult(
                valid=True,
                message="No reference actions - sequence validation skipped"
            )
        
        unexpected_actions = []
        expected_actions_remaining = dict(ctx.reference_actions)
        
        for action_type, count in ctx.actual_actions.items():
            expected_count = expected_actions_remaining.get(action_type, 0)
            
            if count > expected_count:
                # More of this action than expected
                unexpected_actions.append({
                    "action": action_type,
                    "expected": expected_count,
                    "actual": count,
                    "extra": count - expected_count
                })
        
        details = {
            "reference_actions": ctx.reference_actions,
            "actual_actions": ctx.actual_actions,
            "unexpected_actions": unexpected_actions,
        }
        
        if not unexpected_actions:
            return ValidationResult(
                valid=True,
                message="Action sequence matches reference",
                details=details
            )
        
        # Check for common recovery patterns
        recovery_patterns = self._detect_recovery_patterns(unexpected_actions)
        if recovery_patterns:
            details["recovery_patterns"] = recovery_patterns
            return ValidationResult(
                valid=True,
                drift_type=DriftType.ADAPTIVE_RECOVERY,
                message=f"Recovery patterns detected: {recovery_patterns}",
                details=details
            )
        
        return ValidationResult(
            valid=False,
            drift_type=DriftType.SEQUENCE_MISMATCH,
            message=f"Unexpected actions detected: {unexpected_actions}",
            details=details
        )
    
    def _detect_recovery_patterns(self, unexpected_actions: List[Dict]) -> List[str]:
        """Detect known intelligent recovery patterns.
        
        Examples:
        - click_at after type_text_at with press_enter=True (form submission fallback)
        - wait_5_seconds after navigation (page load waiting)
        """
        patterns = []
        
        for action in unexpected_actions:
            action_type = action["action"]
            
            if action_type == "click_at" and action["extra"] == 1:
                patterns.append("single_click_fallback")
            elif action_type == "wait_5_seconds":
                patterns.append("page_load_wait")
        
        return patterns


class ContextRelevanceScorer:
    """Score whether loaded context was actually used.
    
    Detects "context pollution" when static data is loaded but never
    referenced in the agent's reasoning or actions.
    """
    
    def validate(self, ctx: GuardrailContext) -> ValidationResult:
        """
        Validate context relevance.
        
        Returns:
            ValidationResult with context usage scoring
        """
        if not ctx.static_data_loaded:
            return ValidationResult(
                valid=True,
                message="No static data loaded - context validation passed",
                details={
                    "static_data_loaded": False,
                    "relevance_score": 1.0  # Perfect score if not loaded
                }
            )
        
        # Static data was loaded - check if it was used
        if ctx.static_data_referenced_in_reasoning:
            return ValidationResult(
                valid=True,
                message="Static data loaded and used in reasoning",
                details={
                    "static_data_loaded": True,
                    "static_data_used": True,
                    "relevance_score": 1.0
                }
            )
        
        # Context pollution: loaded but not used
        return ValidationResult(
            valid=False,
            drift_type=DriftType.CONTEXT_POLLUTION,
            message="Context pollution: static data loaded but not referenced in reasoning",
            details={
                "static_data_loaded": True,
                "static_data_used": False,
                "relevance_score": 0.0,
                "loaded_content_preview": [s[:100] for s in ctx.static_data_content[:3]]
            }
        )


class GuardrailService:
    """Orchestrates all guardrail validators and collects metrics.
    
    Usage:
        service = GuardrailService()
        ctx = GuardrailContext(...)  # Populated during agent execution
        results = service.validate_all(ctx)
        summary = service.get_summary(results)
    """
    
    def __init__(self):
        self.step_validator = StepCountValidator()
        self.action_validator = ActionSequenceValidator()
        self.context_validator = ContextRelevanceScorer()
    
    def validate_all(self, ctx: GuardrailContext) -> Dict[str, ValidationResult]:
        """Run all validators and return results.
        
        Args:
            ctx: GuardrailContext populated with reference and actual data
            
        Returns:
            Dict mapping validator name to its result
        """
        return {
            "step_count": self.step_validator.validate(ctx),
            "action_sequence": self.action_validator.validate(ctx),
            "context_relevance": self.context_validator.validate(ctx),
        }
    
    def get_summary(self, results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """Generate a summary of all validation results for reporting.
        
        Args:
            results: Dict from validate_all()
            
        Returns:
            Summary dict suitable for session report
        """
        drift_detected = any(
            not r.valid and r.drift_type != DriftType.ADAPTIVE_RECOVERY 
            for r in results.values()
        )
        
        adaptive_recovery = any(
            r.drift_type == DriftType.ADAPTIVE_RECOVERY 
            for r in results.values()
        )
        
        context_pollution = any(
            r.drift_type == DriftType.CONTEXT_POLLUTION 
            for r in results.values()
        )
        
        # Build summary
        summary = {
            "drift_detected": drift_detected,
            "adaptive_recovery": adaptive_recovery,
            "context_pollution": context_pollution,
            "validators": {}
        }
        
        for name, result in results.items():
            summary["validators"][name] = {
                "valid": result.valid,
                "drift_type": result.drift_type.value,
                "message": result.message,
            }
            # Include key details
            if "expected_steps" in result.details:
                summary["step_count_expected"] = result.details["expected_steps"]
                summary["step_count_actual"] = result.details["actual_steps"]
            if "extra_steps" in result.details:
                summary["extra_steps"] = result.details["extra_steps"]
            if "relevance_score" in result.details:
                summary["context_relevance_score"] = result.details["relevance_score"]
            if "static_data_loaded" in result.details:
                summary["static_data_loaded"] = result.details["static_data_loaded"]
        
        return summary


def parse_workflow_for_guardrails(workflow: Dict) -> Dict[str, Any]:
    """Extract reference data from a workflow for guardrail comparison.
    
    Args:
        workflow: Workflow dict from Pinecone (supports json_v2 and legacy formats)
        
    Returns:
        Dict with reference_step_count, reference_actions, reference_urls, reference_final_url
    """
    import json
    
    result = {
        "reference_step_count": None,
        "reference_actions": {},
        "reference_urls": [],
        "reference_final_url": None,
    }
    
    if not workflow:
        return result
    
    is_json_v2 = workflow.get("format") == "json_v2"
    
    # Parse steps to get count
    if is_json_v2:
        try:
            steps_raw = workflow.get("steps", "[]")
            steps = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
            result["reference_step_count"] = len(steps)
            
            # Get final URL from last step
            if steps:
                result["reference_final_url"] = steps[-1].get("url")
        except Exception:
            pass
        
        # Parse actions
        try:
            actions_raw = workflow.get("actions", "{}")
            result["reference_actions"] = json.loads(actions_raw) if isinstance(actions_raw, str) else actions_raw
        except Exception:
            pass
        
        # Parse URLs
        try:
            urls_raw = workflow.get("urls_visited", "[]")
            result["reference_urls"] = json.loads(urls_raw) if isinstance(urls_raw, str) else urls_raw
            if result["reference_urls"]:
                result["reference_final_url"] = result["reference_urls"][-1]
        except Exception:
            pass
    else:
        # Legacy text format - try to extract from system_logs or actions_performed
        logs = workflow.get("system_logs", "")
        if logs:
            # Count "--- STEP X ---" occurrences
            import re
            step_matches = re.findall(r"--- STEP (\d+) ---", logs)
            if step_matches:
                result["reference_step_count"] = int(max(step_matches))
        
        actions_str = workflow.get("actions_performed", "")
        if actions_str:
            # Parse "- action_type: N time(s)" format
            import re
            for match in re.finditer(r"- (\w+): (\d+) time", actions_str):
                result["reference_actions"][match.group(1)] = int(match.group(2))
    
    return result


# Singleton instance
_guardrail_service = None

def get_guardrail_service() -> GuardrailService:
    """Get or create the singleton GuardrailService instance."""
    global _guardrail_service
    if _guardrail_service is None:
        _guardrail_service = GuardrailService()
    return _guardrail_service
