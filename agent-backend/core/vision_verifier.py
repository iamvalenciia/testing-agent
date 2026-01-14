"""
Vision Verifier for Semantic QA Execution.

Uses Gemini Vision models to:
1. Locate elements using visual understanding
2. Verify expected visual states after actions
3. Provide confidence scores for visual matches
4. Generate evidence for pass/fail determinations

CRITICAL: This is the SOURCE OF TRUTH for verification.
Visual verification replaces coordinate/selector based checks.
"""

import base64
import asyncio
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from pathlib import Path

from google import genai
from google.genai import types

logger = structlog.get_logger(__name__)


class VerificationResult(str, Enum):
    """Result of visual verification."""
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"


@dataclass
class ElementLocation:
    """Result of element location via vision."""
    found: bool
    description: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    suggested_action: Optional[str] = None  # How to interact (e.g., "click center of button")


@dataclass
class VisualVerificationResult:
    """Result of visual verification after an action."""
    result: VerificationResult
    confidence: float  # 0.0 to 1.0
    expected: str
    actual_description: str
    reasoning: str
    screenshot_analyzed: bool = True


class VisionVerifier:
    """
    Visual verification engine using Gemini Vision.

    Uses VISION_MODEL for:
    - Element location
    - Visual verification
    - Screen analysis

    Uses a LIGHTWEIGHT model for:
    - Quick sanity checks
    - Confidence scoring

    NOTE: gemini-2.5-computer-use-preview requires Computer Use tools.
    For pure visual analysis (no actions), we use gemini-2.0-flash instead.
    """

    # Model for visual analysis (does NOT require Computer Use tools)
    VISION_MODEL = "gemini-2.0-flash"

    # Secondary lightweight model for quick verification
    SECONDARY_MODEL = "gemini-2.0-flash-lite"

    # Confidence threshold for PASS
    CONFIDENCE_THRESHOLD_PASS = 0.75

    # Confidence threshold for UNCERTAIN (below this is FAIL)
    CONFIDENCE_THRESHOLD_UNCERTAIN = 0.50

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Vision Verifier.

        Args:
            api_key: Google API key. If not provided, uses GOOGLE_API_KEY env var.
        """
        self.client = genai.Client(api_key=api_key)
        self._call_count = 0
        self._total_tokens = 0

    async def locate_element(
        self,
        screenshot_base64: str,
        target_description: str,
        action_context: Optional[str] = None
    ) -> ElementLocation:
        """
        Locate an element in the screenshot using visual understanding.

        Args:
            screenshot_base64: Base64-encoded PNG screenshot
            target_description: Human-readable description of the element
            action_context: Additional context about intended action

        Returns:
            ElementLocation with found status, description, and confidence
        """
        context_hint = ""
        if action_context:
            context_hint = f"\nIntended action: {action_context}"

        prompt = f"""You are a QA automation visual analyzer.

TASK: Locate the following UI element in the screenshot.

TARGET ELEMENT: {target_description}{context_hint}

INSTRUCTIONS:
1. Analyze the screenshot carefully
2. Look for the described element
3. DO NOT use coordinates or CSS selectors
4. Describe WHERE the element is in human terms (e.g., "top right corner", "below the header", "in the login form")
5. Provide confidence level (0.0 to 1.0)

RESPONSE FORMAT (JSON):
{{
    "found": true/false,
    "description": "Human-readable location description",
    "confidence": 0.0-1.0,
    "reasoning": "Why you believe this is/isn't the target element",
    "suggested_action": "How to interact with this element (if found)"
}}

If the element is NOT found, explain what you DO see that might be similar or related."""

        try:
            response = await self._call_vision_model(
                model=self.VISION_MODEL,
                prompt=prompt,
                screenshot_base64=screenshot_base64
            )

            # Parse the response
            result = self._parse_json_response(response)

            return ElementLocation(
                found=result.get("found", False),
                description=result.get("description", "Unable to determine location"),
                confidence=float(result.get("confidence", 0.0)),
                reasoning=result.get("reasoning", "No reasoning provided"),
                suggested_action=result.get("suggested_action")
            )

        except Exception as e:
            logger.error("element_location_failed", error=str(e))
            return ElementLocation(
                found=False,
                description="Error during element location",
                confidence=0.0,
                reasoning=f"Vision model error: {str(e)}"
            )

    async def verify_expected_visual(
        self,
        screenshot_base64: str,
        expected_visual: str,
        action_performed: Optional[str] = None,
        use_lightweight_model: bool = False
    ) -> VisualVerificationResult:
        """
        Verify that the expected visual state is present in the screenshot.

        This is the PRIMARY verification method - the source of truth
        for determining if a test step passed or failed.

        Args:
            screenshot_base64: Base64-encoded PNG screenshot
            expected_visual: Description of what should be visible
            action_performed: The action that was just performed (for context)
            use_lightweight_model: Use faster model for quick checks

        Returns:
            VisualVerificationResult with pass/fail determination
        """
        action_context = ""
        if action_performed:
            action_context = f"\nAction just performed: {action_performed}"

        prompt = f"""You are a QA automation visual verifier.

TASK: Verify that the expected visual state is present in the screenshot.

EXPECTED VISUAL STATE: {expected_visual}{action_context}

VERIFICATION RULES:
1. Analyze the screenshot carefully
2. Compare what you see to the expected state
3. Be STRICT - do not assume success
4. Consider partial matches as UNCERTAIN, not PASS
5. Look for exact visual confirmation of the expected state

RESPONSE FORMAT (JSON):
{{
    "matches": true/false,
    "confidence": 0.0-1.0,
    "actual_description": "What you actually see in the screenshot",
    "reasoning": "Detailed explanation of match/mismatch",
    "missing_elements": ["list of expected elements not found"],
    "unexpected_elements": ["list of unexpected elements found"]
}}

Be thorough and critical. A false positive is worse than a false negative."""

        model = self.SECONDARY_MODEL if use_lightweight_model else self.VISION_MODEL

        try:
            response = await self._call_vision_model(
                model=model,
                prompt=prompt,
                screenshot_base64=screenshot_base64
            )

            result = self._parse_json_response(response)

            matches = result.get("matches", False)
            confidence = float(result.get("confidence", 0.0))

            # Determine verification result based on confidence
            if matches and confidence >= self.CONFIDENCE_THRESHOLD_PASS:
                verification_result = VerificationResult.PASS
            elif confidence >= self.CONFIDENCE_THRESHOLD_UNCERTAIN:
                verification_result = VerificationResult.UNCERTAIN
            else:
                verification_result = VerificationResult.FAIL

            return VisualVerificationResult(
                result=verification_result,
                confidence=confidence,
                expected=expected_visual,
                actual_description=result.get("actual_description", "Unable to describe"),
                reasoning=result.get("reasoning", "No reasoning provided")
            )

        except Exception as e:
            logger.error("visual_verification_failed", error=str(e))
            return VisualVerificationResult(
                result=VerificationResult.FAIL,
                confidence=0.0,
                expected=expected_visual,
                actual_description=f"Error: {str(e)}",
                reasoning=f"Vision model error: {str(e)}",
                screenshot_analyzed=False
            )

    async def quick_sanity_check(
        self,
        screenshot_base64: str,
        check_description: str
    ) -> Tuple[bool, float, str]:
        """
        Perform a quick sanity check using the lightweight model.

        Use this for fast preliminary checks before detailed verification.

        Args:
            screenshot_base64: Base64-encoded PNG screenshot
            check_description: What to check for

        Returns:
            Tuple of (passed, confidence, reasoning)
        """
        prompt = f"""Quick visual check: {check_description}

Look at the screenshot and answer:
1. Is the described state visible? (yes/no)
2. Confidence (0.0-1.0)
3. Brief reason

Response format (JSON):
{{"visible": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}"""

        try:
            response = await self._call_vision_model(
                model=self.SECONDARY_MODEL,
                prompt=prompt,
                screenshot_base64=screenshot_base64
            )

            result = self._parse_json_response(response)
            return (
                result.get("visible", False),
                float(result.get("confidence", 0.0)),
                result.get("reason", "No reason provided")
            )

        except Exception as e:
            logger.error("sanity_check_failed", error=str(e))
            return (False, 0.0, f"Error: {str(e)}")

    async def describe_current_state(
        self,
        screenshot_base64: str
    ) -> str:
        """
        Get a detailed description of the current screen state.

        Useful for debugging and failure analysis.

        Args:
            screenshot_base64: Base64-encoded PNG screenshot

        Returns:
            Human-readable description of the current screen
        """
        prompt = """Describe what you see in this screenshot in detail.

Include:
1. What type of page/screen this appears to be
2. Key UI elements visible (forms, buttons, text, images)
3. Any error messages or notifications
4. The general state of the application

Be objective and thorough."""

        try:
            response = await self._call_vision_model(
                model=self.SECONDARY_MODEL,
                prompt=prompt,
                screenshot_base64=screenshot_base64
            )
            return response

        except Exception as e:
            logger.error("state_description_failed", error=str(e))
            return f"Error describing screen state: {str(e)}"

    async def _call_vision_model(
        self,
        model: str,
        prompt: str,
        screenshot_base64: str
    ) -> str:
        """
        Call the Gemini Vision model with a screenshot.

        Args:
            model: Model identifier
            prompt: Text prompt
            screenshot_base64: Base64-encoded PNG screenshot

        Returns:
            Model response text
        """
        self._call_count += 1

        # Prepare image part
        image_data = base64.b64decode(screenshot_base64)

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model,
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type="image/png"),
                    types.Part.from_text(text=prompt)
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=2048
                )
            )

            if response.text:
                return response.text
            else:
                raise ValueError("Empty response from vision model")

        except Exception as e:
            logger.error(
                "vision_model_call_failed",
                model=model,
                error=str(e)
            )
            raise

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from model response, handling markdown code blocks.

        Args:
            response: Raw model response

        Returns:
            Parsed JSON dictionary
        """
        import json

        # Clean up the response
        text = response.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", response=text[:200], error=str(e))
            # Return empty dict on parse failure
            return {}

    def get_metrics(self) -> Dict[str, Any]:
        """Get verification metrics."""
        return {
            "total_calls": self._call_count,
            "vision_model": self.VISION_MODEL,
            "secondary_model": self.SECONDARY_MODEL
        }


async def save_evidence_screenshot(
    screenshot_base64: str,
    task_id: str,
    step_id: int,
    evidence_type: str,
    output_dir: str = "data/screenshots"
) -> str:
    """
    Save a screenshot as evidence.

    Args:
        screenshot_base64: Base64-encoded PNG screenshot
        task_id: Test execution task ID
        step_id: Step number
        evidence_type: Type of evidence (e.g., "before", "after", "failure")
        output_dir: Directory to save screenshots

    Returns:
        Path to saved screenshot
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"{task_id}_step_{step_id}_{evidence_type}.png"
    filepath = output_path / filename

    try:
        image_data = base64.b64decode(screenshot_base64)
        with open(filepath, "wb") as f:
            f.write(image_data)

        logger.info(
            "evidence_saved",
            filepath=str(filepath),
            step_id=step_id,
            evidence_type=evidence_type
        )

        return str(filepath)

    except Exception as e:
        logger.error("evidence_save_failed", error=str(e))
        raise
