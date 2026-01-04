"""Goal Decomposer Module for Smart Agent.

This module uses Gemini to break complex user goals into atomic sub-tasks,
matches each sub-task to existing indexed workflows, and returns an execution plan.

COST OPTIMIZATION: Uses model_selector for cheapest viable model + skips
LLM for simple goals that can be pattern-matched.
"""
import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY
from model_selector import select_model, TaskType


@dataclass
class SubTask:
    """Represents a decomposed sub-task."""
    action: str  # e.g., "login", "download", "navigate"
    target: str  # e.g., "test environment", "hammer from western"
    original_phrase: str  # The part of the goal this came from
    workflow_match: Optional[Dict] = None  # Matched workflow from Pinecone
    match_score: float = 0.0
    keywords: List[str] = field(default_factory=list)


class GoalDecomposer:
    """
    Decomposes complex user goals into executable sub-tasks.
    
    COST OPTIMIZATION:
    - Uses model_selector to pick cheapest model (gemini-2.0-flash-lite)
    - Skips LLM entirely for simple goals via pattern matching
    
    Uses Gemini to understand user intent and break down combined requests
    like "login and download hammer from western" into atomic steps.
    """
    
    # Common action verbs that indicate separate tasks
    ACTION_VERBS = [
        "login", "log in", "sign in", "signin",
        "download", "export", "save",
        "navigate", "go to", "open", "visit",
        "search", "find", "look for",
        "click", "select", "choose",
        "type", "enter", "fill",
        "copy", "paste",
        "upload", "attach",
    ]
    
    # Conjunctions that typically combine multiple tasks
    TASK_SEPARATORS = ["and", "then", "after that", "also", ",", ";"]
    
    def __init__(self, pinecone_service=None):
        """
        Initialize the goal decomposer.
        
        Args:
            pinecone_service: Optional PineconeService for workflow matching
        """
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.pinecone_service = pinecone_service
    
    def decompose(self, goal: str) -> List[SubTask]:
        """
        Decompose a complex goal into atomic sub-tasks.
        
        COST OPTIMIZATION: Tries pattern matching first to avoid LLM calls.
        
        Args:
            goal: User's natural language goal (e.g., "login and download hammer")
        
        Returns:
            List of SubTask objects, each representing one atomic action
        """
        # COST OPTIMIZATION: Check if this is a simple goal we can handle without LLM
        if self._is_simple_goal(goal):
            print(f"[COST] Skipping LLM - simple goal detected: '{goal[:40]}...'")
            return [SubTask(
                action="execute",
                target=goal,
                original_phrase=goal,
                keywords=self._extract_keywords(goal)
            )]
        
        # First, try quick pattern-based decomposition
        quick_result = self._quick_decompose(goal)
        if quick_result and len(quick_result) > 1:
            print(f"[COST] Pattern decomposition found {len(quick_result)} sub-tasks (no LLM)")
            return self._enrich_subtasks(quick_result)
        
        # If no obvious decomposition, use AI
        ai_result = self._ai_decompose(goal)
        if ai_result:
            print(f"[LLM] AI decomposition found {len(ai_result)} sub-tasks")
            return self._enrich_subtasks(ai_result)
        
        # Fallback: treat as single task
        return [SubTask(
            action="execute",
            target=goal,
            original_phrase=goal,
            keywords=self._extract_keywords(goal)
        )]
    
    def _is_simple_goal(self, goal: str) -> bool:
        """
        COST OPTIMIZATION: Detect simple goals that don't need decomposition.
        
        Simple goals are single-action requests that can be handled directly.
        """
        goal_lower = goal.lower().strip()
        
        # Pattern for simple single-action goals
        simple_patterns = [
            r'^(click|type|navigate|go to|open|visit)\s+',  # Single actions
            r'^(login|logout|submit|refresh|reload|back|forward)\s*$',  # One-word actions
            r'^(scroll|wait|pause)\s*',  # Utility actions
        ]
        
        for pattern in simple_patterns:
            if re.match(pattern, goal_lower):
                return True
        
        # Check if goal has no conjunctions (simple single task)
        has_conjunction = any(sep in goal_lower for sep in [' and ', ' then ', ' after '])
        if not has_conjunction and len(goal.split()) <= 6:
            return True
        
        return False
    
    def _quick_decompose(self, goal: str) -> List[SubTask]:
        """
        Try to decompose using simple pattern matching.
        Faster than AI for obvious cases like "login and download".
        """
        goal_lower = goal.lower()
        subtasks = []
        
        # Split by common separators
        parts = re.split(r'\s+and\s+|\s+then\s+|,\s*|\s*;\s*', goal_lower)
        
        if len(parts) <= 1:
            return []  # No obvious decomposition
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Identify the action verb
            action = "execute"  # default
            for verb in self.ACTION_VERBS:
                if part.startswith(verb) or f" {verb}" in part:
                    action = verb.replace(" ", "_")
                    break
            
            subtasks.append(SubTask(
                action=action,
                target=part,
                original_phrase=part,
                keywords=self._extract_keywords(part)
            ))
        
        return subtasks
    
    def _ai_decompose(self, goal: str) -> List[SubTask]:
        """
        Use Gemini to intelligently decompose the goal.
        Handles complex or ambiguous requests.
        """
        prompt = f"""Analyze this user request and decompose it into atomic sub-tasks.

USER REQUEST: "{goal}"

Rules:
1. Each sub-task should be ONE action (login, navigate, download, etc.)
2. Preserve important details (URLs, names, IDs) in each sub-task
3. Return JSON array of objects with: action, target, keywords
4. If only ONE action is needed, return array with single item
5. Keywords should be important nouns for matching (hammer, western, login, etc.)

Examples:
- "login and download hammer from western" → [
    {{"action": "login", "target": "test environment", "keywords": ["login", "graphite", "connect"]}},
    {{"action": "download", "target": "hammer from western", "keywords": ["download", "hammer", "western"]}}
  ]
- "go to the admin page" → [
    {{"action": "navigate", "target": "admin page", "keywords": ["admin", "page"]}}
  ]

Return ONLY valid JSON array, no explanation:"""

        try:
            # COST OPTIMIZATION: Use cheapest model for decomposition
            model_name = select_model(TaskType.DECOMPOSE)
            
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                )
            )
            
            if not response or not response.text:
                return []
            
            # Parse JSON response
            text = response.text.strip()
            # Clean markdown code blocks
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            
            tasks_data = json.loads(text)
            
            subtasks = []
            for task in tasks_data:
                subtasks.append(SubTask(
                    action=task.get("action", "execute"),
                    target=task.get("target", ""),
                    original_phrase=task.get("target", ""),
                    keywords=task.get("keywords", [])
                ))
            
            return subtasks
            
        except Exception as e:
            print(f"⚠️ AI decomposition failed: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text for matching."""
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "to", "from", "for", "of", "in", "on", "at",
            "and", "or", "but", "with", "this", "that", "these", "those",
            "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might",
            "i", "you", "he", "she", "it", "we", "they",
            "my", "your", "his", "her", "its", "our", "their",
            "please", "now", "go", "file"
        }
        
        # Tokenize and filter
        words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return list(set(keywords))  # Remove duplicates
    
    def _enrich_subtasks(self, subtasks: List[SubTask]) -> List[SubTask]:
        """
        Enrich subtasks with workflow matches from Pinecone.
        
        Now queries ALL 3 namespaces for better decision-making:
        - test_execution_steps: Previously executed workflows
        - test_success_cases: Successful workflow patterns
        - static_data: User-defined static reference data
        
        Args:
            subtasks: List of SubTask to enrich
        
        Returns:
            Same list with workflow_match and match_score populated
        """
        if not self.pinecone_service:
            return subtasks
        
        # Namespaces to search (in priority order)
        SEARCH_NAMESPACES = [
            "test_execution_steps",
            "test_success_cases", 
            "static_data"
        ]
        
        for subtask in subtasks:
            try:
                # Build search query from action + target + keywords
                search_query = f"{subtask.action} {subtask.target}"
                
                # Generate embedding
                from screenshot_embedder import get_embedder
                embedder = get_embedder()
                embedding = embedder.embed_query(search_query)
                
                best_match = None
                best_score = 0.0
                source_namespace = None
                
                # Search each namespace and keep the best match
                for namespace in SEARCH_NAMESPACES:
                    try:
                        if namespace == "static_data":
                            # Static data uses simple query
                            matches = self.pinecone_service.query_static_data(
                                query_embedding=embedding,
                                top_k=3
                            )
                            if matches and matches[0].get("score", 0) >= 0.15:
                                match = matches[0]
                                # Convert static_data format to workflow format
                                match["goal_description"] = match.get("data", "")[:100]
                                if match.get("score", 0) > best_score:
                                    best_match = match
                                    best_score = match.get("score", 0)
                                    source_namespace = namespace
                        else:
                            # Regular namespace search
                            match = self.pinecone_service.get_best_step_for_goal_tiered(
                                embedding, 
                                keywords=subtask.keywords,
                                namespace=namespace
                            )
                            if match and match.get("score", 0) > best_score:
                                best_match = match
                                best_score = match.get("score", 0)
                                source_namespace = namespace
                    except Exception as ns_error:
                        print(f"   ⚠️ Error searching {namespace}: {ns_error}")
                
                if best_match:
                    subtask.workflow_match = best_match
                    subtask.match_score = best_score
                    print(f"   ✅ Matched '{subtask.action}' → '{best_match.get('goal_description', 'N/A')[:50]}' (score: {best_score:.2f}, namespace: {source_namespace})")
                else:
                    print(f"   ⚠️ No match for '{subtask.action}: {subtask.target}'")
                    
            except Exception as e:
                print(f"   ❌ Error matching subtask: {e}")
        
        return subtasks
    
    def get_execution_plan(self, goal: str) -> Dict[str, Any]:
        """
        Get a complete execution plan for a goal.
        
        Returns:
            {
                "original_goal": str,
                "is_decomposed": bool,
                "subtasks": List[SubTask],
                "has_all_matches": bool,
                "needs_user_input": bool,
            }
        """
        subtasks = self.decompose(goal)
        
        has_all_matches = all(st.workflow_match is not None for st in subtasks)
        needs_user_input = not has_all_matches and len(subtasks) > 0
        
        return {
            "original_goal": goal,
            "is_decomposed": len(subtasks) > 1,
            "subtasks": subtasks,
            "has_all_matches": has_all_matches,
            "needs_user_input": needs_user_input,
            "subtask_count": len(subtasks),
        }


# Singleton instance
_decomposer_instance = None

def get_goal_decomposer(pinecone_service=None) -> GoalDecomposer:
    """Get or create the GoalDecomposer singleton."""
    global _decomposer_instance
    if _decomposer_instance is None:
        _decomposer_instance = GoalDecomposer(pinecone_service)
    elif pinecone_service and _decomposer_instance.pinecone_service is None:
        _decomposer_instance.pinecone_service = pinecone_service
    return _decomposer_instance
