"""Pydantic models for API request/response and internal data structures."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum


class ActionType(str, Enum):
    CLICK = "click_at"
    TYPE = "type_text_at"
    NAVIGATE = "navigate"
    SCROLL = "scroll_document"
    KEY_COMBO = "key_combination"
    WAIT = "wait_5_seconds"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    HOVER = "hover_at"
    OPEN_BROWSER = "open_web_browser"
    SEARCH = "search"
    SCROLL_AT = "scroll_at"
    DRAG_DROP = "drag_and_drop"


class ActionStep(BaseModel):
    """Represents a single action taken by the agent."""
    step_number: int
    action_type: str
    args: Dict[str, Any]
    screenshot_path: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    reasoning: Optional[str] = None


class WorkflowCategory(str, Enum):
    """Categories for saved workflows."""
    STEPS = "steps"                    # Reusable navigation steps
    HAMMER_INDEXER = "hammer-indexer"  # Workflow to download/index hammer data
    JIRA_INDEXER = "jira-indexer"      # Workflow to fetch/index Jira tickets
    ZENDESK_INDEXER = "zendesk-indexer"  # Workflow to scrape/index Zendesk docs


class WorkflowRecord(BaseModel):
    """A saved workflow that can be replayed."""
    id: str
    name: str
    description: str
    steps: List[ActionStep]
    created_at: str
    tags: List[str] = []
    category: str = "steps"  # Default to regular steps


class SessionContext(BaseModel):
    """Context that persists across tasks within a session.
    
    This is the MEMORY that allows the agent to remember things
    like copied IDs, previous task results, and conversational context.
    """
    session_id: str
    clipboard: Optional[str] = None  # Last copied text (e.g., company ID)
    last_copied_values: List[str] = []  # History of copied values in order
    task_history: List[Dict[str, Any]] = []  # Summary of previous tasks in this session
    current_url: Optional[str] = None  # Where the browser currently is
    user_instructions: List[str] = []  # All user commands in this session for context
    important_notes: Dict[str, str] = {}  # Key-value pairs for important extracted info
    created_at: Optional[str] = None


class TaskRequest(BaseModel):
    """Request to start a new agent task."""
    goal: str
    start_url: Optional[str] = "about:blank"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class TaskResponse(BaseModel):
    """Response containing task status."""
    task_id: str
    status: TaskStatus
    message: Optional[str] = None


class SaveWorkflowRequest(BaseModel):
    """Request to save the current session as a reusable workflow."""
    task_id: str
    name: str
    description: str
    tags: List[str] = []
    steps: Optional[List[ActionStep]] = None  # Optional: send accumulated steps directly
    # NEW FIELDS for enhanced Pinecone indexing
    namespace: str = "test_execution_steps"  # or "test_success_cases"
    index: str = "steps-index"  # or "hammer-index"
    text: str = ""  # User goals/prompts concatenados
    urls_visited: List[str] = []
    actions_performed: Dict[str, int] = {}
    steps_reference_only: List[Dict[str, Any]] = []  # Reference only - NO x,y coordinates
    user_prompts: List[str] = []  # All user prompts sent during the session


class SaveStaticDataRequest(BaseModel):
    """Request to save static data to the static_data namespace.

    Security: Input is sanitized server-side to prevent injection attacks.
    This namespace stores valuable information that rarely changes (e.g., credentials,
    API keys, configuration values).
    """
    data: str  # Raw user input - will be sanitized before storage


# =============================================================================
# SEMANTIC QA EXECUTION MODELS
# =============================================================================
# These models support the vision-based, semantic QA execution system.
# NO coordinates, NO CSS selectors - only semantic descriptions and visual verification.


class SemanticActionType(str, Enum):
    """Supported semantic actions for QA test execution.

    These actions are executed using visual understanding, not coordinates.
    """
    NAVIGATE = "navigate"       # Navigate to a URL
    INPUT = "input"             # Type text into a field (located visually)
    CLICK = "click"             # Click an element (located visually)
    SELECT = "select"           # Select from dropdown (located visually)
    WAIT = "wait"               # Wait for a condition
    VERIFY = "verify"           # Visual verification only, no action


class StepStatus(str, Enum):
    """Status of a test step execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


class TestStep(BaseModel):
    """A single step in a semantic test plan.

    CRITICAL: No coordinates or CSS selectors allowed.
    All targeting is done via visual/semantic description.
    """
    step_id: int
    action: SemanticActionType
    target: Optional[str] = None           # URL for navigate, None for verify
    target_description: Optional[str] = None  # Visual description of element to interact with
    value: Optional[str] = None            # Input value for input/select actions
    expected_visual: str                   # REQUIRED: Visual verification description
    timeout_seconds: int = 30              # Max time to wait for action

    class Config:
        use_enum_values = True


class TestPlan(BaseModel):
    """A complete semantic test plan for QA execution.

    This is the SOURCE OF TRUTH for test execution.
    Human-readable JSON format with visual verification requirements.
    """
    test_case_id: str
    description: str
    steps: List[TestStep]
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

    def get_step(self, step_id: int) -> Optional[TestStep]:
        """Get a step by its ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


class StepEvidence(BaseModel):
    """Evidence collected during step execution."""
    screenshot_before: Optional[str] = None   # Path to screenshot before action
    screenshot_after: Optional[str] = None    # Path to screenshot after action
    failure_screenshot: Optional[str] = None  # Path to failure evidence screenshot
    visual_match_confidence: Optional[float] = None  # 0.0-1.0 confidence score
    reasoning: Optional[str] = None           # LLM reasoning about the visual match
    element_location_description: Optional[str] = None  # How the element was identified


class StepExecutionResult(BaseModel):
    """Result of executing a single test step."""
    step_id: int
    status: StepStatus
    action: str
    target_description: Optional[str] = None
    expected_visual: str
    actual_visual_description: Optional[str] = None  # What was actually observed
    evidence: Optional[StepEvidence] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_time_ms: int = 0
    timestamp: Optional[str] = None

    class Config:
        use_enum_values = True


class TestPlanExecutionResult(BaseModel):
    """Complete result of test plan execution."""
    test_case_id: str
    description: str
    overall_status: StepStatus
    steps_results: List[StepExecutionResult]
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    total_execution_time_ms: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    class Config:
        use_enum_values = True


class TestPlanExecutionRequest(BaseModel):
    """Request to execute a test plan."""
    test_plan: TestPlan
    start_from_step: int = 1              # Start from this step (for resume)
    stop_on_failure: bool = True          # Stop execution on first failure
    max_retries_per_step: int = 3         # Retry failed steps this many times
    preserve_browser_session: bool = True # Keep browser open between steps


class TestPlanExecutionStatus(BaseModel):
    """Real-time status update during test execution."""
    test_case_id: str
    current_step_id: int
    current_step_status: StepStatus
    overall_progress: float               # 0.0-1.0
    steps_status: Dict[int, StepStatus]   # step_id -> status mapping
    message: Optional[str] = None

    class Config:
        use_enum_values = True

