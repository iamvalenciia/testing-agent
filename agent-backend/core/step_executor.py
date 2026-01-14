"""
Step Executor for Semantic QA Execution.

Executes individual test steps using:
1. Visual element location (via Gemini Vision)
2. Browser automation (via BrowserController)
3. Visual verification (via VisionVerifier)

MANDATORY EXECUTION LOOP (PER STEP):
1. Parse step
2. Interpret intent
3. Capture screenshot
4. Locate element using Gemini Vision
5. Execute action
6. Intelligent wait
7. Verify expected_visual
8. Mark PASS / FAIL
9. Save evidence

NO coordinates, NO CSS selectors - ONLY semantic understanding.
"""

import asyncio
import base64
import time
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable
from pathlib import Path
import structlog

from google import genai
from google.genai import types

from models import (
    TestStep,
    TestPlan,
    StepStatus,
    StepEvidence,
    StepExecutionResult,
    SemanticActionType,
)
from .vision_verifier import (
    VisionVerifier,
    VerificationResult,
    save_evidence_screenshot,
)

logger = structlog.get_logger(__name__)


class StepExecutionError(Exception):
    """Raised when step execution fails."""
    pass


class StepExecutor:
    """
    Executes semantic test steps using vision-based automation.

    This executor:
    - Uses Gemini Vision to locate elements by description
    - Executes actions through browser automation
    - Verifies results visually
    - Manages retries and evidence collection
    """

    # Primary model for computer use actions
    COMPUTER_USE_MODEL = "gemini-2.5-computer-use-preview-10-2025"

    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    RETRY_WAIT_BASE = 2.0  # seconds, will increase with each retry

    def __init__(
        self,
        browser_controller,  # BrowserController instance
        api_key: Optional[str] = None,
        output_dir: str = "data/screenshots",
        on_status_update: Optional[Callable[[int, StepStatus, str], Awaitable[None]]] = None
    ):
        """
        Initialize the Step Executor.

        Args:
            browser_controller: BrowserController instance for browser automation
            api_key: Google API key for Gemini
            output_dir: Directory for saving evidence screenshots
            on_status_update: Async callback for status updates (step_id, status, message)
        """
        self.browser = browser_controller
        self.client = genai.Client(api_key=api_key)
        self.vision_verifier = VisionVerifier(api_key=api_key)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.on_status_update = on_status_update
        self._execution_metrics: Dict[str, Any] = {}

    async def execute_step(
        self,
        step: TestStep,
        task_id: str,
        max_retries: int = DEFAULT_MAX_RETRIES
    ) -> StepExecutionResult:
        """
        Execute a single test step with the mandatory execution loop.

        MANDATORY EXECUTION LOOP:
        1. Parse step - Extract action and intent
        2. Interpret intent - Understand what needs to be done
        3. Capture screenshot - Current state before action
        4. Locate element - Using Gemini Vision (for non-navigate actions)
        5. Execute action - Perform the browser action
        6. Intelligent wait - Wait for page to stabilize
        7. Verify expected_visual - Check if expected state is present
        8. Mark PASS / FAIL - Based on verification
        9. Save evidence - Screenshots and logs

        Args:
            step: TestStep to execute
            task_id: Unique ID for this test execution
            max_retries: Maximum retry attempts on failure

        Returns:
            StepExecutionResult with status, evidence, and details
        """
        start_time = time.time()
        retry_count = 0
        last_error: Optional[str] = None
        evidence = StepEvidence()

        logger.info(
            "step_execution_started",
            step_id=step.step_id,
            action=step.action,
            target_description=step.target_description
        )

        # Notify status update
        if self.on_status_update:
            await self.on_status_update(step.step_id, StepStatus.RUNNING, f"Executing {step.action}")

        while retry_count <= max_retries:
            try:
                # === STEP 1 & 2: Parse and interpret intent ===
                action_intent = self._interpret_step_intent(step)
                logger.debug("step_intent_interpreted", intent=action_intent)

                # === STEP 3: Capture screenshot before action ===
                screenshot_before = await self.browser.get_screenshot_base64()
                evidence.screenshot_before = await save_evidence_screenshot(
                    screenshot_before,
                    task_id,
                    step.step_id,
                    f"before_attempt_{retry_count}",
                    str(self.output_dir)
                )

                # === STEP 4: Locate element using Gemini Vision ===
                if step.action not in [SemanticActionType.NAVIGATE, SemanticActionType.WAIT, SemanticActionType.VERIFY]:
                    if step.target_description:
                        location = await self.vision_verifier.locate_element(
                            screenshot_before,
                            step.target_description,
                            action_context=f"Intending to {step.action}"
                        )

                        if not location.found:
                            raise StepExecutionError(
                                f"Could not locate element: '{step.target_description}'. "
                                f"Reason: {location.reasoning}"
                            )

                        evidence.element_location_description = location.description
                        logger.info(
                            "element_located",
                            step_id=step.step_id,
                            description=location.description,
                            confidence=location.confidence
                        )

                # === STEP 5: Execute action ===
                await self._execute_action(step, screenshot_before)

                # === STEP 6: Intelligent wait ===
                await self._intelligent_wait(step.action)

                # === STEP 7: Verify expected_visual ===
                screenshot_after = await self.browser.get_screenshot_base64()
                evidence.screenshot_after = await save_evidence_screenshot(
                    screenshot_after,
                    task_id,
                    step.step_id,
                    f"after_attempt_{retry_count}",
                    str(self.output_dir)
                )

                verification = await self.vision_verifier.verify_expected_visual(
                    screenshot_after,
                    step.expected_visual,
                    action_performed=f"{step.action} on '{step.target_description or step.target}'"
                )

                evidence.visual_match_confidence = verification.confidence
                evidence.reasoning = verification.reasoning

                # === STEP 8: Mark PASS / FAIL ===
                if verification.result == VerificationResult.PASS:
                    execution_time = int((time.time() - start_time) * 1000)

                    logger.info(
                        "step_execution_passed",
                        step_id=step.step_id,
                        confidence=verification.confidence,
                        execution_time_ms=execution_time
                    )

                    if self.on_status_update:
                        await self.on_status_update(step.step_id, StepStatus.PASS, "Step passed")

                    return StepExecutionResult(
                        step_id=step.step_id,
                        status=StepStatus.PASS,
                        action=step.action,
                        target_description=step.target_description,
                        expected_visual=step.expected_visual,
                        actual_visual_description=verification.actual_description,
                        evidence=evidence,
                        retry_count=retry_count,
                        execution_time_ms=execution_time,
                        timestamp=datetime.utcnow().isoformat()
                    )

                elif verification.result == VerificationResult.UNCERTAIN:
                    # Uncertain - treat as potential failure, retry
                    last_error = f"Uncertain verification: {verification.reasoning}"
                    logger.warning(
                        "step_verification_uncertain",
                        step_id=step.step_id,
                        confidence=verification.confidence,
                        reasoning=verification.reasoning
                    )

                else:
                    # Verification failed
                    last_error = f"Visual verification failed: {verification.reasoning}"
                    logger.warning(
                        "step_verification_failed",
                        step_id=step.step_id,
                        expected=step.expected_visual,
                        actual=verification.actual_description
                    )

                # Save failure evidence
                evidence.failure_screenshot = await save_evidence_screenshot(
                    screenshot_after,
                    task_id,
                    step.step_id,
                    f"failure_attempt_{retry_count}",
                    str(self.output_dir)
                )

            except Exception as e:
                last_error = str(e)
                logger.error(
                    "step_execution_error",
                    step_id=step.step_id,
                    error=last_error,
                    retry_count=retry_count
                )

                # Capture failure screenshot
                try:
                    failure_screenshot = await self.browser.get_screenshot_base64()
                    evidence.failure_screenshot = await save_evidence_screenshot(
                        failure_screenshot,
                        task_id,
                        step.step_id,
                        f"error_attempt_{retry_count}",
                        str(self.output_dir)
                    )
                except Exception:
                    pass

            # Retry logic
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = self.RETRY_WAIT_BASE * retry_count
                logger.info(
                    "step_retry",
                    step_id=step.step_id,
                    retry_count=retry_count,
                    wait_time=wait_time
                )
                if self.on_status_update:
                    await self.on_status_update(
                        step.step_id,
                        StepStatus.RUNNING,
                        f"Retry {retry_count}/{max_retries} after {wait_time}s"
                    )
                await asyncio.sleep(wait_time)

        # === STEP 9: All retries exhausted - FAIL ===
        execution_time = int((time.time() - start_time) * 1000)

        logger.error(
            "step_execution_failed",
            step_id=step.step_id,
            total_retries=retry_count - 1,
            final_error=last_error
        )

        if self.on_status_update:
            await self.on_status_update(step.step_id, StepStatus.FAIL, last_error or "Unknown error")

        return StepExecutionResult(
            step_id=step.step_id,
            status=StepStatus.FAIL,
            action=step.action,
            target_description=step.target_description,
            expected_visual=step.expected_visual,
            actual_visual_description=last_error,
            evidence=evidence,
            error_message=last_error,
            retry_count=retry_count - 1,
            execution_time_ms=execution_time,
            timestamp=datetime.utcnow().isoformat()
        )

    def _interpret_step_intent(self, step: TestStep) -> str:
        """Interpret the intent of a test step for logging and debugging."""
        action = step.action

        if action == SemanticActionType.NAVIGATE:
            return f"Navigate browser to {step.target}"
        elif action == SemanticActionType.INPUT:
            masked_value = "********" if "password" in (step.target_description or "").lower() else step.value
            return f"Enter '{masked_value}' into {step.target_description}"
        elif action == SemanticActionType.CLICK:
            return f"Click on {step.target_description}"
        elif action == SemanticActionType.SELECT:
            return f"Select '{step.value}' from {step.target_description}"
        elif action == SemanticActionType.WAIT:
            return f"Wait for condition: {step.expected_visual}"
        elif action == SemanticActionType.VERIFY:
            return f"Verify visual state: {step.expected_visual}"
        else:
            return f"Unknown action: {action}"

    async def _execute_action(self, step: TestStep, screenshot_base64: str) -> None:
        """
        Execute the browser action for a step using Gemini Computer Use.

        This method uses the Gemini Computer Use model to:
        1. Understand the current screen state
        2. Identify the target element visually
        3. Execute the appropriate action

        Args:
            step: TestStep to execute
            screenshot_base64: Current screenshot for visual understanding
        """
        action = step.action

        if action == SemanticActionType.NAVIGATE:
            # Direct navigation - no vision needed
            await self.browser.execute_action("navigate", {"url": step.target})
            return

        if action == SemanticActionType.WAIT:
            # Wait action - just wait for the timeout
            await asyncio.sleep(min(step.timeout_seconds, 30))
            return

        if action == SemanticActionType.VERIFY:
            # Verify action - no browser action needed, verification happens later
            return

        # For input, click, select - use Gemini Computer Use
        await self._execute_with_computer_use(step, screenshot_base64)

    async def _execute_with_computer_use(self, step: TestStep, screenshot_base64: str) -> None:
        """
        Execute an action using Gemini Computer Use model.

        The model analyzes the screenshot and executes the action
        using its built-in computer use capabilities.
        """
        # Build the action prompt
        if step.action == SemanticActionType.INPUT:
            action_prompt = f"""You are controlling a browser. Look at the screenshot and:

1. Find the element described as: "{step.target_description}"
2. Click on it to focus it
3. Type the text: "{step.value}"

DO NOT press Enter unless specifically instructed.
Execute this action now."""

        elif step.action == SemanticActionType.CLICK:
            action_prompt = f"""You are controlling a browser. Look at the screenshot and:

1. Find the element described as: "{step.target_description}"
2. Click on it

Execute this action now."""

        elif step.action == SemanticActionType.SELECT:
            action_prompt = f"""You are controlling a browser. Look at the screenshot and:

1. Find the dropdown/select element described as: "{step.target_description}"
2. Click on it to open the options
3. Select the option: "{step.value}"

Execute this action now."""

        else:
            raise StepExecutionError(f"Unsupported action for computer use: {step.action}")

        # Call Gemini Computer Use
        try:
            image_data = base64.b64decode(screenshot_base64)

            # Configure the Computer Use tool - REQUIRED for gemini-2.5-computer-use model
            computer_use_tool = types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER
                )
            )

            # Structure content with text FIRST, then image (required order for Computer Use)
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=action_prompt),
                        types.Part.from_bytes(data=image_data, mime_type="image/png")
                    ]
                )
            ]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.COMPUTER_USE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[computer_use_tool],
                    temperature=0.1,
                    max_output_tokens=1024
                )
            )

            # Parse the response for actions
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    # Check if this is a function call (computer use action)
                    if hasattr(part, 'function_call') and part.function_call:
                        await self._execute_computer_use_action(part.function_call)
                    elif hasattr(part, 'text') and part.text:
                        # Log the model's reasoning
                        logger.debug("computer_use_reasoning", text=part.text[:500])

        except Exception as e:
            logger.error("computer_use_failed", error=str(e))
            raise StepExecutionError(f"Computer use execution failed: {str(e)}")

    async def _execute_computer_use_action(self, function_call) -> None:
        """
        Execute a computer use function call from Gemini.

        Maps Gemini's computer use actions to browser controller actions.
        """
        action_name = function_call.name
        args = dict(function_call.args) if function_call.args else {}

        logger.debug(
            "executing_computer_use_action",
            action=action_name,
            args=args
        )

        # Map computer use actions to browser controller
        if action_name == "click":
            # Computer use provides x, y coordinates
            if "x" in args and "y" in args:
                await self.browser.execute_action("click_at", {
                    "x": int(args["x"] * 1000 / 1440),  # Normalize to 0-1000
                    "y": int(args["y"] * 1000 / 900)
                })

        elif action_name == "type":
            text = args.get("text", "")
            await self.browser.page.keyboard.type(text)

        elif action_name == "key":
            key = args.get("key", "")
            await self.browser.page.keyboard.press(key)

        elif action_name == "scroll":
            direction = args.get("direction", "down")
            await self.browser.execute_action("scroll_document", {"direction": direction})

        else:
            logger.warning("unknown_computer_use_action", action=action_name)

    async def _intelligent_wait(self, action: SemanticActionType) -> None:
        """
        Intelligent wait after action execution.

        Waits for the page to stabilize based on the action type.
        """
        # Base wait
        base_wait = 0.5

        # Action-specific waits
        if action == SemanticActionType.NAVIGATE:
            # Wait longer for navigation
            try:
                await self.browser.page.wait_for_load_state("domcontentloaded", timeout=10000)
                await self.browser.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            base_wait = 1.0

        elif action == SemanticActionType.CLICK:
            # Click might trigger navigation or modal
            base_wait = 1.0
            try:
                await self.browser.page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

        elif action == SemanticActionType.INPUT:
            # Input might trigger validation
            base_wait = 0.3

        elif action == SemanticActionType.SELECT:
            # Select might trigger dependent changes
            base_wait = 0.5

        await asyncio.sleep(base_wait)

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics."""
        return {
            **self._execution_metrics,
            "vision_verifier_metrics": self.vision_verifier.get_metrics()
        }


class SemanticActionExecutor:
    """
    Alternative executor that uses pure semantic prompts without coordinate mapping.

    This executor sends natural language instructions to Gemini Computer Use
    and lets it handle all visual understanding and action execution.
    """

    MODEL = "gemini-2.5-computer-use-preview-10-2025"

    def __init__(self, browser_controller, api_key: Optional[str] = None):
        self.browser = browser_controller
        self.client = genai.Client(api_key=api_key)

    async def execute_semantic_action(
        self,
        action: str,
        target_description: str,
        value: Optional[str] = None,
        expected_result: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a semantic action using natural language only.

        Args:
            action: Action type (click, input, select, etc.)
            target_description: Visual description of target element
            value: Value to input/select if applicable
            expected_result: Expected visual result for verification

        Returns:
            Result dictionary with success status and details
        """
        # Capture current screenshot
        screenshot_base64 = await self.browser.get_screenshot_base64()
        image_data = base64.b64decode(screenshot_base64)

        # Build semantic prompt
        prompt = self._build_semantic_prompt(action, target_description, value, expected_result)

        try:
            # Configure the Computer Use tool - REQUIRED for gemini-2.5-computer-use model
            computer_use_tool = types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER
                )
            )

            # Structure content with text FIRST, then image (required order for Computer Use)
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_data, mime_type="image/png")
                    ]
                )
            ]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[computer_use_tool],
                    temperature=0.1,
                    max_output_tokens=2048
                )
            )

            # Process response
            return await self._process_response(response)

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _build_semantic_prompt(
        self,
        action: str,
        target_description: str,
        value: Optional[str],
        expected_result: Optional[str]
    ) -> str:
        """Build a semantic prompt for the action."""
        prompt_parts = [
            "QA TEST EXECUTION — SEMANTIC MODE",
            "",
            "RULES:",
            "- Use ONLY visual understanding",
            "- Do NOT assume coordinates",
            "- Verify the action visually",
            "",
            f"ACTION: {action}",
            f"TARGET: {target_description}",
        ]

        if value:
            prompt_parts.append(f"VALUE: {value}")

        if expected_result:
            prompt_parts.append(f"EXPECTED RESULT: {expected_result}")

        prompt_parts.extend([
            "",
            "Execute this action and report:",
            "1. Whether you found the target element",
            "2. The action you performed",
            "3. What you observe after the action"
        ])

        return "\n".join(prompt_parts)

    async def _process_response(self, response) -> Dict[str, Any]:
        """Process the Gemini response and extract results."""
        result = {
            "success": True,
            "actions_taken": [],
            "observations": ""
        }

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    # Execute the action
                    action_result = await self._execute_function_call(part.function_call)
                    result["actions_taken"].append(action_result)
                elif hasattr(part, 'text') and part.text:
                    result["observations"] = part.text

        return result

    async def _execute_function_call(self, function_call) -> Dict[str, Any]:
        """Execute a function call from the model."""
        action_name = function_call.name
        args = dict(function_call.args) if function_call.args else {}

        # Map to browser controller actions
        if action_name == "click":
            await self.browser.execute_action("click_at", {
                "x": int(args.get("x", 500) * 1000 / 1440),
                "y": int(args.get("y", 500) * 1000 / 900)
            })
        elif action_name == "type":
            await self.browser.page.keyboard.type(args.get("text", ""))
        elif action_name == "key":
            await self.browser.page.keyboard.press(args.get("key", ""))
        elif action_name == "scroll":
            await self.browser.execute_action("scroll_document", {
                "direction": args.get("direction", "down")
            })

        return {
            "action": action_name,
            "args": args
        }
