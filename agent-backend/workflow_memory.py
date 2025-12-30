"""Workflow Memory - Episodic memory for learned workflows.

This module provides episodic memory capabilities, storing learned workflows
as "recipes" that can be retrieved and adapted for similar tasks. This enables
the agent to learn from demonstration and improve over time.

Key features:
- Store workflows as high-level steps (intentions, not code)
- Retrieve similar workflows using semantic search
- Adapt stored workflows to new UI states using visual grounding
"""

import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from screenshot_embedder import get_embedder
from pinecone_service import PineconeService, IndexType


class ActionType(str, Enum):
    """Types of actions in a workflow step."""
    CLICK = "click"              # Click on an element
    TYPE = "type"                # Type text into a field
    NAVIGATE = "navigate"        # Navigate to a URL
    WAIT = "wait_for"            # Wait for a visual cue
    TOOL_CALL = "tool_call"      # Call an external tool (Mailpit, Hammer)
    SCROLL = "scroll"            # Scroll the page
    SCREENSHOT = "screenshot"    # Take a screenshot
    ASSERT = "assert"            # Assert something is visible


@dataclass
class WorkflowStep:
    """
    A single step in a learned workflow.
    
    Steps are described in terms of intentions, not CSS selectors.
    This makes them resilient to UI changes.
    """
    action: ActionType
    target_desc: str              # Visual description of target element
    value_source: Optional[str] = None   # e.g., "ticket.supplier_name" or literal value
    tool_name: Optional[str] = None      # For TOOL_CALL actions
    tool_args: Optional[Dict[str, Any]] = None
    wait_timeout: int = 10        # For WAIT actions
    screenshot_path: Optional[str] = None  # Screenshot taken at this step
    reasoning: Optional[str] = None  # Why this step was taken
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action.value if isinstance(self.action, ActionType) else self.action,
            "target_desc": self.target_desc,
            "value_source": self.value_source,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "wait_timeout": self.wait_timeout,
            "screenshot_path": self.screenshot_path,
            "reasoning": self.reasoning
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        """Create from dictionary."""
        action = data.get("action", "click")
        if isinstance(action, str):
            try:
                action = ActionType(action)
            except ValueError:
                action = ActionType.CLICK
        
        return cls(
            action=action,
            target_desc=data.get("target_desc", ""),
            value_source=data.get("value_source"),
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            wait_timeout=data.get("wait_timeout", 10),
            screenshot_path=data.get("screenshot_path"),
            reasoning=data.get("reasoning")
        )


@dataclass
class WorkflowMemory:
    """
    A complete learned workflow (recipe).
    
    Stores the high-level procedure for completing a task,
    with trigger keywords for retrieval.
    """
    workflow_name: str
    trigger_keywords: List[str]
    description: str
    steps: List[WorkflowStep]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    success_count: int = 0
    failure_count: int = 0
    
    @property
    def workflow_id(self) -> str:
        """Generate stable ID from workflow name."""
        return hashlib.md5(self.workflow_name.lower().encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "trigger_keywords": self.trigger_keywords,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "success_count": self.success_count,
            "failure_count": self.failure_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowMemory":
        """Create from dictionary."""
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            workflow_name=data.get("workflow_name", ""),
            trigger_keywords=data.get("trigger_keywords", []),
            description=data.get("description", ""),
            steps=steps,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0)
        )


class EpisodicMemoryManager:
    """
    Manages workflow learning and retrieval.
    
    Provides methods to:
    - Save new workflows from demonstrations
    - Find similar workflows for new tasks
    - Adapt workflows to current UI state
    """
    
    def __init__(self, pinecone_service: Optional[PineconeService] = None):
        """
        Initialize the memory manager.
        
        Args:
            pinecone_service: Optional PineconeService instance
        """
        self.pinecone = pinecone_service or PineconeService()
        self.embedder = get_embedder()
    
    def _generate_workflow_text(self, workflow: WorkflowMemory) -> str:
        """Generate searchable text from workflow for embedding."""
        parts = [
            f"Workflow: {workflow.workflow_name}",
            f"Description: {workflow.description}",
            f"Keywords: {', '.join(workflow.trigger_keywords)}",
            "Steps:"
        ]
        
        for i, step in enumerate(workflow.steps, 1):
            step_text = f"  {i}. {step.action.value}: {step.target_desc}"
            if step.value_source:
                step_text += f" (value: {step.value_source})"
            if step.tool_name:
                step_text += f" [tool: {step.tool_name}]"
            parts.append(step_text)
        
        return "\n".join(parts)
    
    async def save_workflow(self, workflow: WorkflowMemory) -> str:
        """
        Save a workflow to episodic memory (Pinecone).
        
        Args:
            workflow: The workflow to save
        
        Returns:
            The workflow ID
        """
        workflow.updated_at = datetime.now().isoformat()
        
        # Generate embedding for the workflow
        workflow_text = self._generate_workflow_text(workflow)
        embedding = self.embedder.embed_query(workflow_text)
        
        # Prepare metadata
        metadata = {
            "workflow_name": workflow.workflow_name,
            "description": workflow.description,
            "trigger_keywords": ", ".join(workflow.trigger_keywords),
            "step_count": len(workflow.steps),
            "steps_json": json.dumps([s.to_dict() for s in workflow.steps]),
            "success_count": workflow.success_count,
            "failure_count": workflow.failure_count,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at
        }
        
        # Upsert to Pinecone
        index = self.pinecone.get_index(IndexType.WORKFLOWS)
        index.upsert(vectors=[{
            "id": workflow.workflow_id,
            "values": embedding,
            "metadata": metadata
        }])
        
        print(f"📚 Saved workflow: '{workflow.workflow_name}' ({len(workflow.steps)} steps)")
        return workflow.workflow_id
    
    async def find_similar_workflow(
        self, 
        query: str, 
        top_k: int = 3,
        min_score: float = 0.3
    ) -> List[WorkflowMemory]:
        """
        Search for workflows similar to the query.
        
        Args:
            query: Natural language description of what to do
            top_k: Number of results to return
            min_score: Minimum similarity score
        
        Returns:
            List of matching WorkflowMemory objects
        """
        # Generate query embedding
        embedding = self.embedder.embed_query(query)
        
        # Query Pinecone
        matches = self.pinecone.query_index(
            IndexType.WORKFLOWS,
            embedding,
            top_k=top_k
        )
        
        results = []
        for match in matches:
            if match.score < min_score:
                continue
            
            # Parse steps from JSON
            try:
                steps_json = match.metadata.get("steps_json", "[]")
                steps_data = json.loads(steps_json)
                steps = [WorkflowStep.from_dict(s) for s in steps_data]
            except json.JSONDecodeError:
                steps = []
            
            workflow = WorkflowMemory(
                workflow_name=match.metadata.get("workflow_name", ""),
                trigger_keywords=match.metadata.get("trigger_keywords", "").split(", "),
                description=match.metadata.get("description", ""),
                steps=steps,
                created_at=match.metadata.get("created_at", ""),
                updated_at=match.metadata.get("updated_at", ""),
                success_count=match.metadata.get("success_count", 0),
                failure_count=match.metadata.get("failure_count", 0)
            )
            
            results.append(workflow)
            print(f"🔍 Found workflow: '{workflow.workflow_name}' (score: {match.score:.2f})")
        
        return results
    
    async def get_best_workflow(
        self, 
        query: str,
        min_score: float = 0.5
    ) -> Optional[WorkflowMemory]:
        """
        Get the single best matching workflow.
        
        Args:
            query: What the user wants to do
            min_score: Minimum similarity threshold
        
        Returns:
            Best matching workflow or None
        """
        workflows = await self.find_similar_workflow(query, top_k=1, min_score=min_score)
        return workflows[0] if workflows else None
    
    async def record_result(
        self, 
        workflow_id: str, 
        success: bool
    ):
        """
        Record whether a workflow execution succeeded or failed.
        
        Used to track workflow reliability over time.
        """
        # In a production system, you'd update the metadata in Pinecone
        # For now, just log it
        status = "✅ success" if success else "❌ failure"
        print(f"📊 Workflow {workflow_id}: {status}")
    
    def create_workflow_from_steps(
        self,
        name: str,
        description: str,
        keywords: List[str],
        raw_steps: List[Dict[str, Any]]
    ) -> WorkflowMemory:
        """
        Create a WorkflowMemory from raw step data.
        
        Args:
            name: Workflow name
            description: What this workflow does
            keywords: Trigger keywords for search
            raw_steps: List of step dictionaries
        
        Returns:
            WorkflowMemory object
        """
        steps = [WorkflowStep.from_dict(s) for s in raw_steps]
        return WorkflowMemory(
            workflow_name=name,
            trigger_keywords=keywords,
            description=description,
            steps=steps
        )
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from memory."""
        try:
            index = self.pinecone.get_index(IndexType.WORKFLOWS)
            index.delete(ids=[workflow_id])
            print(f"🗑️ Deleted workflow: {workflow_id}")
            return True
        except Exception as e:
            print(f"⚠️ Could not delete workflow: {e}")
            return False


# Singleton instance
_memory_manager: Optional[EpisodicMemoryManager] = None


def get_memory_manager() -> EpisodicMemoryManager:
    """Get the singleton EpisodicMemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = EpisodicMemoryManager()
    return _memory_manager
