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

