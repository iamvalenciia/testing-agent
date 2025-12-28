"""Storage service for saving and loading workflow recordings."""
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from models import WorkflowRecord, ActionStep

# Directory to store workflow JSON files
WORKFLOWS_DIR = Path(__file__).parent / "data" / "workflows"
SCREENSHOTS_DIR = Path(__file__).parent / "data" / "screenshots"


def ensure_directories():
    """Create storage directories if they don't exist."""
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def save_screenshot(task_id: str, step_number: int, screenshot_bytes: bytes) -> str:
    """Save a screenshot and return the file path."""
    ensure_directories()
    filename = f"{task_id}_step_{step_number}.png"
    filepath = SCREENSHOTS_DIR / filename
    with open(filepath, "wb") as f:
        f.write(screenshot_bytes)
    return str(filepath)


def save_workflow(workflow: WorkflowRecord) -> str:
    """Save a workflow record to disk."""
    ensure_directories()
    filepath = WORKFLOWS_DIR / f"{workflow.id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(workflow.model_dump(), f, indent=2, ensure_ascii=False)
    return str(filepath)


def load_workflow(workflow_id: str) -> Optional[WorkflowRecord]:
    """Load a workflow by ID."""
    filepath = WORKFLOWS_DIR / f"{workflow_id}.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return WorkflowRecord(**data)


def list_workflows() -> List[Dict[str, Any]]:
    """List all saved workflows (metadata only)."""
    ensure_directories()
    workflows = []
    for filepath in WORKFLOWS_DIR.glob("*.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            workflows.append({
                "id": data.get("id"),
                "name": data.get("name"),
                "description": data.get("description"),
                "created_at": data.get("created_at"),
                "tags": data.get("tags", []),
                "step_count": len(data.get("steps", []))
            })
    return sorted(workflows, key=lambda x: x.get("created_at", ""), reverse=True)


def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow by ID."""
    filepath = WORKFLOWS_DIR / f"{workflow_id}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
