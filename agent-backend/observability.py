"""
Observability configuration for the Computer Use Agent backend.

Provides:
- Structured logging via structlog (JSON format)
- Prometheus metrics for monitoring
- Request context propagation (trace_id, session_id)
"""
import logging
import sys
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Optional
import time

import structlog
from prometheus_client import Counter, Histogram, Gauge

# =============================================================================
# CONTEXT VARIABLES - For request/session context propagation
# =============================================================================
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
task_id_var: ContextVar[str] = ContextVar("task_id", default="")


# =============================================================================
# SESSION METRICS - Per-session tracking for real-time UI display
# =============================================================================
class SessionMetrics:
    """
    Per-session metrics that can be sent to frontend in real-time.
    
    Unlike global Prometheus metrics, these are scoped to a single WebSocket session
    and reset when the session ends. They are sent via WebSocket to the Report Modal.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.started_at = time.time()
        
        # Counters (per-session)
        self.websocket_messages_sent = 0
        self.websocket_messages_received = 0
        self.agent_tasks_started = 0
        self.agent_tasks_completed = 0
        self.agent_tasks_failed = 0
        self.agent_turns = 0
        self.gemini_api_calls = 0
        self.browser_actions = 0
        self.pinecone_queries = 0
        
        # Timing (accumulative seconds)
        self.total_agent_turn_duration = 0.0
        self.total_gemini_api_duration = 0.0
        self.total_browser_action_duration = 0.0
        
        # Guardrail results (populated after task completion)
        self.guardrail_results = {
            "step_count_expected": None,
            "step_count_actual": 0,
            "extra_steps": [],
            "drift_detected": False,
            "adaptive_recovery": False,
            "static_data_loaded": False,
            "static_data_used": False,
            "context_pollution": False,
            "validators": {},
        }
    
    def record_message_sent(self):
        """Record a WebSocket message sent."""
        self.websocket_messages_sent += 1
    
    def record_message_received(self):
        """Record a WebSocket message received."""
        self.websocket_messages_received += 1
    
    def record_task_started(self):
        """Record an agent task starting."""
        self.agent_tasks_started += 1
    
    def record_task_completed(self):
        """Record an agent task completing successfully."""
        self.agent_tasks_completed += 1
    
    def record_task_failed(self):
        """Record an agent task failing."""
        self.agent_tasks_failed += 1
    
    def record_agent_turn(self, duration_seconds: float = 0.0):
        """Record an agent turn with optional duration."""
        self.agent_turns += 1
        self.total_agent_turn_duration += duration_seconds
    
    def record_gemini_call(self, duration_seconds: float = 0.0):
        """Record a Gemini API call with duration."""
        self.gemini_api_calls += 1
        self.total_gemini_api_duration += duration_seconds
    
    def record_browser_action(self, duration_seconds: float = 0.0):
        """Record a browser action with duration."""
        self.browser_actions += 1
        self.total_browser_action_duration += duration_seconds
    
    def record_pinecone_query(self):
        """Record a Pinecone query."""
        self.pinecone_queries += 1
    
    def record_guardrail_result(self, summary: dict):
        """Record guardrail validation results.
        
        Args:
            summary: Dict from GuardrailService.get_summary()
        """
        self.guardrail_results.update(summary)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for WebSocket transmission."""
        elapsed = time.time() - self.started_at
        return {
            "session_id": self.session_id,
            "elapsed_seconds": round(elapsed, 1),
            "websocket_messages": {
                "sent": self.websocket_messages_sent,
                "received": self.websocket_messages_received,
            },
            "agent": {
                "tasks_started": self.agent_tasks_started,
                "tasks_completed": self.agent_tasks_completed,
                "tasks_failed": self.agent_tasks_failed,
                "turns": self.agent_turns,
                "avg_turn_duration_seconds": round(
                    self.total_agent_turn_duration / max(1, self.agent_turns), 2
                ),
            },
            "gemini_api": {
                "calls": self.gemini_api_calls,
                "total_duration_seconds": round(self.total_gemini_api_duration, 2),
                "avg_duration_seconds": round(
                    self.total_gemini_api_duration / max(1, self.gemini_api_calls), 2
                ),
            },
            "browser": {
                "actions": self.browser_actions,
                "total_duration_seconds": round(self.total_browser_action_duration, 2),
            },
            "pinecone": {
                "queries": self.pinecone_queries,
            },
            "guardrails": self.guardrail_results,
        }


def generate_trace_id() -> str:
    """Generate a new trace ID."""
    return uuid.uuid4().hex[:16]


def bind_context(
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None:
    """Bind context variables for the current async context."""
    if trace_id:
        trace_id_var.set(trace_id)
    if session_id:
        session_id_var.set(session_id)
    if task_id:
        task_id_var.set(task_id)


def get_context() -> dict:
    """Get current context for logging."""
    ctx = {}
    if trace_id := trace_id_var.get():
        ctx["trace_id"] = trace_id
    if session_id := session_id_var.get():
        ctx["session_id"] = session_id
    if task_id := task_id_var.get():
        ctx["task_id"] = task_id
    return ctx


# =============================================================================
# STRUCTLOG CONFIGURATION
# =============================================================================
def add_context_processor(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Add context variables to every log entry."""
    event_dict.update(get_context())
    return event_dict


def configure_logging(json_format: bool = True, log_level: str = "INFO") -> None:
    """
    Configure structured logging with structlog.
    
    Args:
        json_format: If True, output JSON logs. If False, output colored console logs.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_context_processor,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if json_format:
        # Production: JSON format for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Also configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    """Get a logger instance bound with the given name."""
    return structlog.get_logger(name)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

# HTTP Request Metrics (handled by prometheus-fastapi-instrumentator)

# WebSocket Metrics
WEBSOCKET_CONNECTIONS = Gauge(
    "websocket_connections_active",
    "Number of active WebSocket connections",
)
WEBSOCKET_MESSAGES = Counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    ["direction", "message_type"],  # direction: sent/received, message_type: start/stop/step/etc
)

# Agent Metrics
AGENT_TASKS = Counter(
    "agent_tasks_total",
    "Total agent tasks started",
    ["status"],  # status: started/completed/failed/cancelled
)
AGENT_TURN_DURATION = Histogram(
    "agent_turn_duration_seconds",
    "Duration of each agent turn",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)
AGENT_TURNS_PER_TASK = Histogram(
    "agent_turns_per_task",
    "Number of turns per task",
    buckets=[1, 2, 5, 10, 20, 50, 100],
)

# Pinecone Metrics
PINECONE_QUERY_DURATION = Histogram(
    "pinecone_query_duration_seconds",
    "Duration of Pinecone queries",
    ["operation", "namespace"],  # operation: query/upsert/delete
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)
PINECONE_QUERIES = Counter(
    "pinecone_queries_total",
    "Total Pinecone operations",
    ["operation", "namespace", "status"],
)

# Gemini API Metrics
GEMINI_API_CALLS = Counter(
    "gemini_api_calls_total",
    "Total Gemini API calls",
    ["model", "status"],  # status: success/error
)
GEMINI_API_DURATION = Histogram(
    "gemini_api_duration_seconds",
    "Gemini API call duration",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
GEMINI_TOKENS = Counter(
    "gemini_tokens_total",
    "Gemini token consumption",
    ["type"],  # type: input/output
)

# Browser Metrics
BROWSER_ACTIONS = Counter(
    "browser_actions_total",
    "Total browser actions executed",
    ["action_type", "status"],  # action_type: click/type/scroll/etc
)
BROWSER_ACTION_DURATION = Histogram(
    "browser_action_duration_seconds",
    "Browser action duration",
    ["action_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# Workflow Metrics
WORKFLOW_SAVES = Counter(
    "workflow_saves_total",
    "Total workflow save operations",
    ["namespace", "status"],
)


# =============================================================================
# TIMING DECORATOR
# =============================================================================
def timed(
    metric: Histogram,
    labels: Optional[dict] = None,
):
    """Decorator to time function execution and record to Prometheus histogram."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def asyncio_iscoroutinefunction(func: Any) -> bool:
    """Check if function is an async function."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# =============================================================================
# INITIALIZATION
# =============================================================================
# Configure logging on module import (development mode by default)
# In production, set OBSERVABILITY_JSON_LOGS=true
import os

_json_format = os.getenv("OBSERVABILITY_JSON_LOGS", "false").lower() == "true"
_log_level = os.getenv("OBSERVABILITY_LOG_LEVEL", "INFO")

configure_logging(json_format=_json_format, log_level=_log_level)

# Default logger instance
log = get_logger("agent-backend")
