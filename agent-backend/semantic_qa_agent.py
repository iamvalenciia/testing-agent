"""
Semantic QA Execution Agent.

This agent executes human-readable JSON test plans using:
- Visual understanding (Gemini Vision)
- Semantic element targeting (no coordinates)
- Visual verification (source of truth)
- Deterministic, auditable results

ARCHITECTURAL SHIFT:
❌ Coordinate replay
❌ CSS selectors
❌ DOM-only assumptions
❌ Action logs as truth

✅ Semantic intent
✅ Vision-based targeting
✅ Visual verification as source of truth
✅ Human-readable test plans

This agent behaves like:
"A junior QA engineer executing a written test case, looking at the screen,
verifying outcomes, and stopping when something looks wrong — but powered by Gemini Vision."
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Optional, Callable, Awaitable, List, Dict, Any, Union
import structlog

from models import (
    TestPlan,
    TestStep,
    TestPlanExecutionRequest,
    TestPlanExecutionResult,
    TestPlanExecutionStatus,
    StepExecutionResult,
    StepStatus,
    StepEvidence,
    SemanticActionType,
)
from browser import BrowserController
from core.test_plan_parser import TestPlanParser
from core.vision_verifier import VisionVerifier, save_evidence_screenshot
from core.step_executor import StepExecutor
from observability import (
    log as obs_logger,
    SessionMetrics,
)

logger = structlog.get_logger(__name__)


class SemanticQAAgent:
    """
    Autonomous QA Execution Agent using Semantic Understanding.

    This agent:
    1. Consumes human-readable JSON test plans
    2. Executes actions using visual understanding
    3. Verifies outcomes visually before continuing
    4. Produces structured evidence and execution logs

    Execution Protocol (per step):
    1. Parse step intent
    2. Capture screenshot (before)
    3. Locate element using Gemini Vision
    4. Execute action
    5. Intelligent wait
    6. Capture screenshot (after)
    7. Verify expected_visual
    8. Mark PASS/FAIL with evidence
    """

    def __init__(
        self,
        browser: Optional[BrowserController] = None,
        api_key: Optional[str] = None,
        output_dir: str = "data/screenshots",
        on_step_status: Optional[Callable[[int, StepStatus, str], Awaitable[None]]] = None,
        on_execution_status: Optional[Callable[[TestPlanExecutionStatus], Awaitable[None]]] = None,
        on_screenshot: Optional[Callable[[int, str], Awaitable[None]]] = None,  # (step_id, screenshot_b64)
        session_metrics: Optional[SessionMetrics] = None,
    ):
        """
        Initialize the Semantic QA Agent.

        Args:
            browser: BrowserController instance (will be created if not provided)
            api_key: Google API key for Gemini
            output_dir: Directory for saving evidence screenshots
            on_step_status: Callback for step status updates (step_id, status, message)
            on_execution_status: Callback for overall execution status
            on_screenshot: Callback to send screenshots to UI
            session_metrics: Session metrics for observability
        """
        self.browser = browser or BrowserController()
        self._owns_browser = browser is None
        self.api_key = api_key
        self.output_dir = output_dir

        # Callbacks
        self.on_step_status = on_step_status
        self.on_execution_status = on_execution_status
        self.on_screenshot = on_screenshot
        self.session_metrics = session_metrics

        # Components
        self.parser = TestPlanParser()
        self.vision_verifier = VisionVerifier(api_key=api_key)
        self.step_executor: Optional[StepExecutor] = None

        # State
        self.current_execution_id: Optional[str] = None
        self.current_test_plan: Optional[TestPlan] = None
        self._stop_requested = False
        self._is_running = False

    async def execute_test_plan(
        self,
        test_plan: Union[TestPlan, Dict, str],
        start_from_step: int = 1,
        stop_on_failure: bool = True,
        max_retries_per_step: int = 3,
    ) -> TestPlanExecutionResult:
        """
        Execute a complete test plan.

        Args:
            test_plan: TestPlan object, JSON dict, or path to JSON file
            start_from_step: Start execution from this step (for resume)
            stop_on_failure: Stop execution on first failure
            max_retries_per_step: Maximum retries for each step

        Returns:
            TestPlanExecutionResult with complete execution details
        """
        # Parse test plan if needed
        if isinstance(test_plan, (dict, str)):
            test_plan = self.parser.parse(test_plan)

        self.current_test_plan = test_plan
        self.current_execution_id = str(uuid.uuid4())
        self._stop_requested = False
        self._is_running = True

        logger.info(
            "test_plan_execution_started",
            execution_id=self.current_execution_id,
            test_case_id=test_plan.test_case_id,
            total_steps=len(test_plan.steps),
            start_from_step=start_from_step
        )

        # Initialize step executor
        self.step_executor = StepExecutor(
            browser_controller=self.browser,
            api_key=self.api_key,
            output_dir=self.output_dir,
            on_status_update=self._handle_step_status_update
        )

        # Start browser if needed
        if not self.browser.is_started:
            await self.browser.start()

        # Initialize tracking
        started_at = datetime.utcnow().isoformat()
        steps_results: List[StepExecutionResult] = []
        steps_status: Dict[int, StepStatus] = {
            step.step_id: StepStatus.PENDING for step in test_plan.steps
        }

        # Execute steps
        overall_status = StepStatus.PASS
        failed_step_id: Optional[int] = None

        for step in test_plan.steps:
            # Skip steps before start_from_step
            if step.step_id < start_from_step:
                steps_results.append(StepExecutionResult(
                    step_id=step.step_id,
                    status=StepStatus.SKIPPED,
                    action=step.action,
                    target_description=step.target_description,
                    expected_visual=step.expected_visual,
                    timestamp=datetime.utcnow().isoformat()
                ))
                steps_status[step.step_id] = StepStatus.SKIPPED
                continue

            # Check for stop request
            if self._stop_requested:
                logger.info("execution_stopped_by_request", step_id=step.step_id)
                # Mark remaining steps as skipped
                for remaining_step in test_plan.steps:
                    if remaining_step.step_id >= step.step_id:
                        steps_results.append(StepExecutionResult(
                            step_id=remaining_step.step_id,
                            status=StepStatus.SKIPPED,
                            action=remaining_step.action,
                            target_description=remaining_step.target_description,
                            expected_visual=remaining_step.expected_visual,
                            timestamp=datetime.utcnow().isoformat()
                        ))
                        steps_status[remaining_step.step_id] = StepStatus.SKIPPED
                break

            # Notify execution status
            await self._notify_execution_status(
                test_plan.test_case_id,
                step.step_id,
                StepStatus.RUNNING,
                steps_status
            )

            # Execute the step
            result = await self.step_executor.execute_step(
                step,
                self.current_execution_id,
                max_retries=max_retries_per_step
            )

            steps_results.append(result)
            steps_status[step.step_id] = result.status

            # Send screenshot to UI with step_id
            if self.on_screenshot and result.evidence and result.evidence.screenshot_after:
                try:
                    # Read screenshot and send to UI with step_id
                    import base64
                    with open(result.evidence.screenshot_after, 'rb') as f:
                        screenshot_b64 = base64.b64encode(f.read()).decode('utf-8')
                    await self.on_screenshot(step.step_id, screenshot_b64)
                except Exception as e:
                    logger.warning("screenshot_send_failed", error=str(e), step_id=step.step_id)

            # Check for failure
            if result.status == StepStatus.FAIL:
                overall_status = StepStatus.FAIL
                failed_step_id = step.step_id

                if stop_on_failure:
                    logger.info(
                        "execution_stopped_on_failure",
                        step_id=step.step_id,
                        error=result.error_message
                    )
                    # Mark remaining steps as skipped
                    for remaining_step in test_plan.steps:
                        if remaining_step.step_id > step.step_id:
                            steps_results.append(StepExecutionResult(
                                step_id=remaining_step.step_id,
                                status=StepStatus.SKIPPED,
                                action=remaining_step.action,
                                target_description=remaining_step.target_description,
                                expected_visual=remaining_step.expected_visual,
                                timestamp=datetime.utcnow().isoformat()
                            ))
                            steps_status[remaining_step.step_id] = StepStatus.SKIPPED
                    break

        # Calculate summary
        completed_at = datetime.utcnow().isoformat()
        passed_steps = sum(1 for r in steps_results if r.status == StepStatus.PASS)
        failed_steps = sum(1 for r in steps_results if r.status == StepStatus.FAIL)
        skipped_steps = sum(1 for r in steps_results if r.status == StepStatus.SKIPPED)
        total_execution_time = sum(r.execution_time_ms for r in steps_results)

        # Final status notification
        await self._notify_execution_status(
            test_plan.test_case_id,
            steps_results[-1].step_id if steps_results else 0,
            overall_status,
            steps_status,
            message=f"Execution complete: {passed_steps} passed, {failed_steps} failed, {skipped_steps} skipped"
        )

        self._is_running = False

        result = TestPlanExecutionResult(
            test_case_id=test_plan.test_case_id,
            description=test_plan.description,
            overall_status=overall_status,
            steps_results=steps_results,
            total_steps=len(test_plan.steps),
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            total_execution_time_ms=total_execution_time,
            started_at=started_at,
            completed_at=completed_at
        )

        logger.info(
            "test_plan_execution_completed",
            test_case_id=test_plan.test_case_id,
            overall_status=overall_status,
            passed=passed_steps,
            failed=failed_steps,
            skipped=skipped_steps,
            total_time_ms=total_execution_time
        )

        return result

    async def execute_single_step(
        self,
        step: Union[TestStep, Dict],
        task_id: Optional[str] = None,
        max_retries: int = 3
    ) -> StepExecutionResult:
        """
        Execute a single test step.

        Useful for:
        - Running individual steps
        - Re-running failed steps
        - Step-by-step debugging

        Args:
            step: TestStep object or dict
            task_id: Task ID for evidence naming
            max_retries: Maximum retries

        Returns:
            StepExecutionResult
        """
        # Parse step if dict
        if isinstance(step, dict):
            step = TestStep(**step)

        task_id = task_id or str(uuid.uuid4())

        # Initialize step executor if needed
        if not self.step_executor:
            self.step_executor = StepExecutor(
                browser_controller=self.browser,
                api_key=self.api_key,
                output_dir=self.output_dir,
                on_status_update=self._handle_step_status_update
            )

        # Start browser if needed
        if not self.browser.is_started:
            await self.browser.start()

        return await self.step_executor.execute_step(step, task_id, max_retries)

    async def resume_from_step(
        self,
        test_plan: Union[TestPlan, Dict, str],
        step_id: int,
        stop_on_failure: bool = True,
        max_retries_per_step: int = 3,
    ) -> TestPlanExecutionResult:
        """
        Resume test plan execution from a specific step.

        Args:
            test_plan: Test plan to resume
            step_id: Step ID to resume from
            stop_on_failure: Stop on failure
            max_retries_per_step: Max retries per step

        Returns:
            TestPlanExecutionResult
        """
        return await self.execute_test_plan(
            test_plan,
            start_from_step=step_id,
            stop_on_failure=stop_on_failure,
            max_retries_per_step=max_retries_per_step
        )

    def stop(self):
        """Request the agent to stop after the current step."""
        self._stop_requested = True
        logger.info("stop_requested")

    @property
    def is_running(self) -> bool:
        """Check if the agent is currently running."""
        return self._is_running

    async def get_current_screenshot(self) -> Optional[str]:
        """Get the current browser screenshot as base64."""
        if self.browser.is_started:
            return await self.browser.get_screenshot_base64()
        return None

    async def _handle_step_status_update(
        self,
        step_id: int,
        status: StepStatus,
        message: str
    ):
        """Handle step status updates from the executor."""
        if self.on_step_status:
            await self.on_step_status(step_id, status, message)

    async def _notify_execution_status(
        self,
        test_case_id: str,
        current_step_id: int,
        current_step_status: StepStatus,
        steps_status: Dict[int, StepStatus],
        message: Optional[str] = None
    ):
        """Notify execution status to callback."""
        if self.on_execution_status:
            total_steps = len(steps_status)
            completed_steps = sum(
                1 for s in steps_status.values()
                if s in [StepStatus.PASS, StepStatus.FAIL, StepStatus.SKIPPED]
            )
            progress = completed_steps / total_steps if total_steps > 0 else 0

            status = TestPlanExecutionStatus(
                test_case_id=test_case_id,
                current_step_id=current_step_id,
                current_step_status=current_step_status,
                overall_progress=progress,
                steps_status=steps_status,
                message=message
            )

            await self.on_execution_status(status)

    def get_execution_prompt(self, test_plan: TestPlan) -> str:
        """
        Generate the internal prompt for Gemini Vision.

        This is the prompt structure used internally for semantic execution.
        """
        return self.parser.generate_execution_prompt(test_plan)

    async def close(self):
        """Close the agent and release resources."""
        if self._owns_browser and self.browser:
            await self.browser.stop()
        self._is_running = False


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_semantic_qa_agent(
    browser: Optional[BrowserController] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> SemanticQAAgent:
    """
    Factory function to create a SemanticQAAgent.

    Args:
        browser: Optional BrowserController
        api_key: Google API key
        **kwargs: Additional arguments for SemanticQAAgent

    Returns:
        Configured SemanticQAAgent instance
    """
    from config import GOOGLE_API_KEY
    return SemanticQAAgent(
        browser=browser,
        api_key=api_key or GOOGLE_API_KEY,
        **kwargs
    )


# =============================================================================
# EXECUTION HELPERS
# =============================================================================

async def run_test_plan_from_file(
    file_path: str,
    headless: bool = False,
    stop_on_failure: bool = True
) -> TestPlanExecutionResult:
    """
    Convenience function to run a test plan from a JSON file.

    Args:
        file_path: Path to JSON test plan file
        headless: Run browser in headless mode
        stop_on_failure: Stop on first failure

    Returns:
        TestPlanExecutionResult
    """
    from config import GOOGLE_API_KEY

    # Create browser
    browser = BrowserController()

    # Create agent
    agent = SemanticQAAgent(
        browser=browser,
        api_key=GOOGLE_API_KEY
    )

    try:
        # Execute test plan
        result = await agent.execute_test_plan(
            file_path,
            stop_on_failure=stop_on_failure
        )
        return result
    finally:
        await agent.close()


async def validate_test_plan(
    test_plan: Union[Dict, str]
) -> Dict[str, Any]:
    """
    Validate a test plan without executing it.

    Args:
        test_plan: Test plan dict or JSON string

    Returns:
        Validation result with parsed plan or errors
    """
    parser = TestPlanParser()

    try:
        parsed = parser.parse(test_plan)
        return {
            "valid": True,
            "test_case_id": parsed.test_case_id,
            "description": parsed.description,
            "total_steps": len(parsed.steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "target_description": s.target_description,
                    "expected_visual": s.expected_visual
                }
                for s in parsed.steps
            ]
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "errors": getattr(e, 'errors', [])
        }
