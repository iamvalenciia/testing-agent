"""Tests for the Guardrails service.

Tests cover:
- StepCountValidator: step count matching and drift detection
- ActionSequenceValidator: action sequence validation and recovery detection
- ContextRelevanceScorer: static data usage validation
- parse_workflow_for_guardrails: workflow parsing for both formats
"""
import pytest
from guardrails import (
    GuardrailContext,
    GuardrailService,
    StepCountValidator,
    ActionSequenceValidator,
    ContextRelevanceScorer,
    DriftType,
    parse_workflow_for_guardrails,
    get_guardrail_service,
)


class TestStepCountValidator:
    """Tests for StepCountValidator."""
    
    def test_exact_match(self):
        """Same steps = no drift."""
        validator = StepCountValidator()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=4,
            task_completed_successfully=True,
        )
        result = validator.validate(ctx)
        assert result.valid is True
        assert result.drift_type == DriftType.NONE
    
    def test_within_tolerance(self):
        """±1 step should be acceptable."""
        validator = StepCountValidator()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=5,  # +1 is within tolerance
            task_completed_successfully=True,
        )
        result = validator.validate(ctx)
        assert result.valid is True
    
    def test_extra_steps_drift(self):
        """Extra steps beyond tolerance = drift flagged."""
        validator = StepCountValidator()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=6,
            actual_steps=[
                {"action_type": "navigate", "url": "https://example.com"},
                {"action_type": "type_text_at", "url": "https://example.com"},
                {"action_type": "type_text_at", "url": "https://example.com"},
                {"action_type": "click_at", "url": "https://example.com"},
                {"action_type": "click_at", "url": "https://example.com/dashboard"},  # extra
                {"action_type": "wait_5_seconds", "url": "https://example.com/dashboard"},  # extra
            ],
            task_completed_successfully=False,
        )
        result = validator.validate(ctx)
        assert result.valid is False
        assert result.drift_type == DriftType.EXTRA_STEPS
        assert "extra_steps" in result.details
    
    def test_adaptive_recovery_not_drift(self):
        """Extra steps with correct outcome = adaptive recovery, not drift."""
        validator = StepCountValidator()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=6,
            reference_final_url="https://example.com/dashboard",
            actual_final_url="https://example.com/dashboard",
            actual_steps=[
                {"action_type": "navigate"},
                {"action_type": "type_text_at"},
                {"action_type": "type_text_at"},
                {"action_type": "click_at"},
                {"action_type": "click_at"},  # extra but outcome correct
                {"action_type": "wait_5_seconds"},  # extra but outcome correct
            ],
            task_completed_successfully=True,
        )
        result = validator.validate(ctx)
        assert result.valid is True  # Not blocking
        assert result.drift_type == DriftType.ADAPTIVE_RECOVERY
        assert result.details.get("adaptive_recovery") is True
    
    def test_no_reference_skips_validation(self):
        """Without reference, validation is skipped."""
        validator = StepCountValidator()
        ctx = GuardrailContext(
            reference_step_count=None,
            actual_step_count=10,
        )
        result = validator.validate(ctx)
        assert result.valid is True
        assert "skipped" in result.message.lower()


class TestActionSequenceValidator:
    """Tests for ActionSequenceValidator."""
    
    def test_sequence_match(self):
        """Actions match reference = no drift."""
        validator = ActionSequenceValidator()
        ctx = GuardrailContext(
            reference_actions={"navigate": 1, "type_text_at": 2, "click_at": 1},
            actual_actions={"navigate": 1, "type_text_at": 2, "click_at": 1},
        )
        result = validator.validate(ctx)
        assert result.valid is True
    
    def test_single_click_fallback_recovery(self):
        """Single extra click is recognized as fallback recovery."""
        validator = ActionSequenceValidator()
        ctx = GuardrailContext(
            reference_actions={"navigate": 1, "type_text_at": 2},
            actual_actions={"navigate": 1, "type_text_at": 2, "click_at": 1},  # 1 extra click
        )
        result = validator.validate(ctx)
        assert result.valid is True
        assert "single_click_fallback" in result.details.get("recovery_patterns", [])
    
    def test_no_reference_skips_validation(self):
        """Without reference, validation is skipped."""
        validator = ActionSequenceValidator()
        ctx = GuardrailContext(
            reference_actions={},
            actual_actions={"click_at": 10},
        )
        result = validator.validate(ctx)
        assert result.valid is True


class TestContextRelevanceScorer:
    """Tests for ContextRelevanceScorer."""
    
    def test_no_static_data_loaded(self):
        """No static data loaded = perfect score."""
        validator = ContextRelevanceScorer()
        ctx = GuardrailContext(
            static_data_loaded=False,
        )
        result = validator.validate(ctx)
        assert result.valid is True
        assert result.details.get("relevance_score") == 1.0
    
    def test_static_data_loaded_and_used(self):
        """Static data loaded AND used = no pollution."""
        validator = ContextRelevanceScorer()
        ctx = GuardrailContext(
            static_data_loaded=True,
            static_data_content=["Company: Western Digital, ID: US66254"],
            static_data_referenced_in_reasoning=True,
        )
        result = validator.validate(ctx)
        assert result.valid is True
        assert result.drift_type == DriftType.NONE
    
    def test_context_pollution(self):
        """Static data loaded but NOT used = pollution flagged."""
        validator = ContextRelevanceScorer()
        ctx = GuardrailContext(
            static_data_loaded=True,
            static_data_content=["Company: Western Digital, ID: US66254"],
            static_data_referenced_in_reasoning=False,
        )
        result = validator.validate(ctx)
        assert result.valid is False
        assert result.drift_type == DriftType.CONTEXT_POLLUTION
        assert result.details.get("relevance_score") == 0.0


class TestWorkflowParsing:
    """Tests for parse_workflow_for_guardrails."""
    
    def test_json_v2_format(self):
        """Parse json_v2 format workflow."""
        import json
        workflow = {
            "format": "json_v2",
            "steps": json.dumps([
                {"step": 1, "url": "about:blank"},
                {"step": 2, "url": "https://example.com/login"},
                {"step": 3, "url": "https://example.com/login"},
                {"step": 4, "url": "https://example.com/dashboard"},
            ]),
            "actions": json.dumps({"navigate": 1, "type_text_at": 2, "click_at": 1}),
            "urls_visited": json.dumps(["about:blank", "https://example.com/login", "https://example.com/dashboard"]),
        }
        result = parse_workflow_for_guardrails(workflow)
        assert result["reference_step_count"] == 4
        assert result["reference_actions"] == {"navigate": 1, "type_text_at": 2, "click_at": 1}
        assert result["reference_final_url"] == "https://example.com/dashboard"
    
    def test_legacy_text_format(self):
        """Parse legacy text format workflow."""
        workflow = {
            "system_logs": "--- STEP 1 ---\n--- STEP 2 ---\n--- STEP 3 ---\n--- STEP 4 ---\n",
            "actions_performed": "- navigate: 1 time(s)\n- type_text_at: 2 time(s)\n- click_at: 1 time(s)",
        }
        result = parse_workflow_for_guardrails(workflow)
        assert result["reference_step_count"] == 4
        assert result["reference_actions"]["navigate"] == 1
        assert result["reference_actions"]["type_text_at"] == 2
    
    def test_empty_workflow(self):
        """Empty workflow returns empty reference."""
        result = parse_workflow_for_guardrails({})
        assert result["reference_step_count"] is None
        assert result["reference_actions"] == {}


class TestGuardrailService:
    """Tests for the orchestrating GuardrailService."""
    
    def test_validate_all(self):
        """Service runs all validators."""
        service = get_guardrail_service()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=4,
            reference_actions={"navigate": 1},
            actual_actions={"navigate": 1},
            static_data_loaded=False,
            task_completed_successfully=True,
        )
        results = service.validate_all(ctx)
        assert "step_count" in results
        assert "action_sequence" in results
        assert "context_relevance" in results
        assert all(r.valid for r in results.values())
    
    def test_summary_no_drift(self):
        """Summary with no drift."""
        service = get_guardrail_service()
        ctx = GuardrailContext(
            reference_step_count=4,
            actual_step_count=4,
            task_completed_successfully=True,
        )
        results = service.validate_all(ctx)
        summary = service.get_summary(results)
        assert summary["drift_detected"] is False
        assert summary["adaptive_recovery"] is False
        assert summary["context_pollution"] is False
    
    def test_summary_with_pollution(self):
        """Summary flags context pollution."""
        service = get_guardrail_service()
        ctx = GuardrailContext(
            static_data_loaded=True,
            static_data_content=["Some data"],
            static_data_referenced_in_reasoning=False,  # Pollution!
        )
        results = service.validate_all(ctx)
        summary = service.get_summary(results)
        assert summary["context_pollution"] is True


class TestLazyLoadKeywords:
    """Tests for lazy loading keyword detection."""
    
    def test_login_no_trigger(self):
        """'login' should NOT trigger static data loading."""
        goal = "login"
        goal_lower = goal.lower()
        static_keywords = ["company id", "download hammer", "western", "adobe", "vonage", "company_id", "get the id"]
        needs_static_lookup = any(kw in goal_lower for kw in static_keywords)
        assert needs_static_lookup is False
    
    def test_hammer_download_trigger(self):
        """'download hammer from western' should trigger static data loading."""
        goal = "download hammer from western"
        goal_lower = goal.lower()
        static_keywords = ["company id", "download hammer", "western", "adobe", "vonage", "company_id", "get the id"]
        needs_static_lookup = any(kw in goal_lower for kw in static_keywords)
        assert needs_static_lookup is True
    
    def test_company_id_trigger(self):
        """'get the company id for adobe' should trigger static data loading."""
        goal = "get the company id for adobe"
        goal_lower = goal.lower()
        static_keywords = ["company id", "download hammer", "western", "adobe", "vonage", "company_id", "get the id"]
        needs_static_lookup = any(kw in goal_lower for kw in static_keywords)
        assert needs_static_lookup is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
