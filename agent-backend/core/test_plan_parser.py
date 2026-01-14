"""
Test Plan Parser for Semantic QA Execution.

Parses human-readable JSON test plans and validates them
against the semantic execution schema.

CRITICAL: This parser enforces NO coordinates, NO CSS selectors.
Only semantic descriptions and visual verification requirements are allowed.
"""

import json
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import structlog

from models import (
    TestPlan,
    TestStep,
    SemanticActionType,
)

logger = structlog.get_logger(__name__)


class TestPlanParserError(Exception):
    """Raised when test plan parsing fails."""
    pass


class TestPlanValidationError(Exception):
    """Raised when test plan validation fails."""

    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


class TestPlanParser:
    """
    Parser for semantic test plans.

    Validates and converts JSON test plans into TestPlan objects
    that can be executed by the SemanticQAAgent.

    Example test plan format:
    {
        "test_case_id": "TC-001-LOGIN",
        "description": "Verify login flow and dashboard access",
        "steps": [
            {
                "step_id": 1,
                "action": "navigate",
                "target": "https://app.example.com/login",
                "expected_visual": "Login form visible with email and password fields"
            },
            {
                "step_id": 2,
                "action": "input",
                "target_description": "Email input field",
                "value": "user@test.com",
                "expected_visual": "Email text visible inside the input field"
            }
        ]
    }
    """

    SUPPORTED_ACTIONS = {action.value for action in SemanticActionType}

    # Fields that indicate coordinate-based or selector-based targeting (FORBIDDEN)
    FORBIDDEN_FIELDS = {
        "x", "y", "coordinates", "coords",
        "selector", "css_selector", "xpath", "id", "class_name",
        "element_id", "dom_path", "pixel_x", "pixel_y",
    }

    def __init__(self):
        self._validation_errors: List[str] = []

    def parse(self, source: Union[str, Dict, Path]) -> TestPlan:
        """
        Parse a test plan from various sources.

        Args:
            source: JSON string, dict, or path to JSON file

        Returns:
            Validated TestPlan object

        Raises:
            TestPlanParserError: If parsing fails
            TestPlanValidationError: If validation fails
        """
        self._validation_errors = []

        # Load the raw data
        raw_data = self._load_source(source)

        # Validate the structure
        self._validate_structure(raw_data)

        # Validate each step
        steps_data = raw_data.get("steps", [])
        validated_steps = []

        for idx, step_data in enumerate(steps_data):
            try:
                validated_step = self._validate_and_parse_step(step_data, idx + 1)
                validated_steps.append(validated_step)
            except Exception as e:
                self._validation_errors.append(f"Step {idx + 1}: {str(e)}")

        # Check for validation errors
        if self._validation_errors:
            raise TestPlanValidationError(
                f"Test plan validation failed with {len(self._validation_errors)} error(s)",
                self._validation_errors
            )

        # Create the TestPlan object
        try:
            test_plan = TestPlan(
                test_case_id=raw_data["test_case_id"],
                description=raw_data["description"],
                steps=validated_steps,
                tags=raw_data.get("tags", []),
                metadata=raw_data.get("metadata", {})
            )

            logger.info(
                "test_plan_parsed",
                test_case_id=test_plan.test_case_id,
                total_steps=len(test_plan.steps),
                description=test_plan.description[:100]
            )

            return test_plan

        except Exception as e:
            raise TestPlanParserError(f"Failed to create TestPlan: {str(e)}")

    def _load_source(self, source: Union[str, Dict, Path]) -> Dict:
        """Load raw data from various source types."""
        if isinstance(source, dict):
            return source

        if isinstance(source, Path):
            source = str(source)

        if isinstance(source, str):
            # Check if it's a file path
            if source.endswith(".json") or "/" in source or "\\" in source:
                try:
                    path = Path(source)
                    if path.exists():
                        with open(path, "r", encoding="utf-8") as f:
                            return json.load(f)
                except Exception as e:
                    raise TestPlanParserError(f"Failed to read file: {str(e)}")

            # Try to parse as JSON string
            try:
                return json.loads(source)
            except json.JSONDecodeError as e:
                raise TestPlanParserError(f"Invalid JSON: {str(e)}")

        raise TestPlanParserError(f"Unsupported source type: {type(source)}")

    def _validate_structure(self, data: Dict) -> None:
        """Validate the top-level structure of the test plan."""
        required_fields = ["test_case_id", "description", "steps"]

        for field in required_fields:
            if field not in data:
                self._validation_errors.append(f"Missing required field: {field}")

        if "steps" in data:
            if not isinstance(data["steps"], list):
                self._validation_errors.append("'steps' must be an array")
            elif len(data["steps"]) == 0:
                self._validation_errors.append("'steps' array cannot be empty")

    def _validate_and_parse_step(self, step_data: Dict, position: int) -> TestStep:
        """
        Validate and parse a single step.

        Enforces semantic-only targeting - no coordinates or selectors allowed.
        """
        # Check for forbidden fields (coordinates, selectors)
        for field in self.FORBIDDEN_FIELDS:
            if field in step_data:
                raise ValueError(
                    f"Forbidden field '{field}' detected. "
                    "Semantic QA execution does NOT use coordinates or CSS selectors. "
                    "Use 'target_description' for visual element identification."
                )

        # Validate required fields
        if "action" not in step_data:
            raise ValueError("Missing required field 'action'")

        if "expected_visual" not in step_data:
            raise ValueError(
                "Missing required field 'expected_visual'. "
                "Visual verification is MANDATORY for every step."
            )

        # Validate action type
        action = step_data["action"].lower()
        if action not in self.SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unsupported action '{action}'. "
                f"Supported actions: {', '.join(sorted(self.SUPPORTED_ACTIONS))}"
            )

        # Use provided step_id or position
        step_id = step_data.get("step_id", position)

        # Validate action-specific requirements
        self._validate_action_requirements(action, step_data)

        # Create TestStep
        return TestStep(
            step_id=step_id,
            action=SemanticActionType(action),
            target=step_data.get("target"),
            target_description=step_data.get("target_description"),
            value=step_data.get("value"),
            expected_visual=step_data["expected_visual"],
            timeout_seconds=step_data.get("timeout_seconds", 30)
        )

    def _validate_action_requirements(self, action: str, step_data: Dict) -> None:
        """Validate action-specific requirements."""
        if action == "navigate":
            if not step_data.get("target"):
                raise ValueError("'navigate' action requires 'target' (URL)")

            target = step_data["target"]
            if not target.startswith(("http://", "https://", "about:")):
                raise ValueError(
                    f"Invalid URL '{target}'. Must start with http://, https://, or about:"
                )

        elif action == "input":
            if not step_data.get("target_description"):
                raise ValueError(
                    "'input' action requires 'target_description' "
                    "(visual description of the input field)"
                )
            if step_data.get("value") is None:
                raise ValueError("'input' action requires 'value' (text to enter)")

        elif action == "click":
            if not step_data.get("target_description"):
                raise ValueError(
                    "'click' action requires 'target_description' "
                    "(visual description of the element to click)"
                )

        elif action == "select":
            if not step_data.get("target_description"):
                raise ValueError(
                    "'select' action requires 'target_description' "
                    "(visual description of the dropdown)"
                )
            if step_data.get("value") is None:
                raise ValueError("'select' action requires 'value' (option to select)")

    def generate_execution_prompt(self, test_plan: TestPlan) -> str:
        """
        Generate the execution prompt for the Gemini Vision model.

        This prompt is injected into the agent to enable semantic execution mode.
        """
        steps_text = []
        for step in test_plan.steps:
            step_lines = [
                f"STEP {step.step_id}:",
                f"  Action: {step.action}",
            ]
            if step.target:
                step_lines.append(f"  Target URL: {step.target}")
            if step.target_description:
                step_lines.append(f"  Target Element: {step.target_description}")
            if step.value:
                # Mask password values
                display_value = "********" if "password" in (step.target_description or "").lower() else step.value
                step_lines.append(f"  Value: {display_value}")
            step_lines.append(f"  Expected Visual: {step.expected_visual}")
            steps_text.append("\n".join(step_lines))

        prompt = f"""QA TEST PLAN — SEMANTIC EXECUTION MODE

You are an autonomous QA Automation Engineer.
You operate using visual understanding only.

RULES:
- Do NOT assume success
- Verify visually after every action
- Do NOT use coordinates or selectors
- Retry failures up to 3 times
- Capture evidence on failure
- STOP if expected visual is not confirmed

TEST CASE: {test_plan.test_case_id}
DESCRIPTION: {test_plan.description}

EXECUTION STEPS:
{chr(10).join(steps_text)}

EXECUTION PROTOCOL:
1. For each step:
   a. Capture current screenshot
   b. Identify target element using VISUAL UNDERSTANDING
   c. Execute the action
   d. Wait for page to stabilize
   e. Capture verification screenshot
   f. Verify expected_visual is present
   g. Report PASS or FAIL with evidence

2. On FAILURE:
   - Capture failure evidence screenshot
   - Describe what you actually see vs. what was expected
   - Retry up to 3 times with increasing wait
   - If still failing, mark step as FAIL and stop

Begin execution from Step 1."""

        return prompt

    @staticmethod
    def create_sample_test_plan() -> Dict:
        """
        Create a sample test plan for reference.

        This can be used as a template for creating new test plans.
        """
        return {
            "test_case_id": "TC-001-LOGIN",
            "description": "Verify login flow and dashboard access",
            "tags": ["smoke", "login", "critical"],
            "metadata": {
                "author": "QA Team",
                "version": "1.0"
            },
            "steps": [
                {
                    "step_id": 1,
                    "action": "navigate",
                    "target": "https://app.example.com/login",
                    "expected_visual": "Login form visible with email and password fields"
                },
                {
                    "step_id": 2,
                    "action": "input",
                    "target_description": "Email input field",
                    "value": "user@test.com",
                    "expected_visual": "Email text visible inside the input field"
                },
                {
                    "step_id": 3,
                    "action": "input",
                    "target_description": "Password input field",
                    "value": "SecurePass123",
                    "expected_visual": "Password field shows masked characters"
                },
                {
                    "step_id": 4,
                    "action": "click",
                    "target_description": "Blue 'Sign In' button",
                    "expected_visual": "Main dashboard visible with user greeting"
                }
            ]
        }
