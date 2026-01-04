"""Pinecone service for managing multiple indexes with different retention policies."""
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from pinecone import Pinecone, ServerlessSpec

from config import MRL_DIMENSION


class IndexType(str, Enum):
    """Types of Pinecone indexes with different retention policies."""
    HAMMER = "hammer-index"       # Hammer config - resets per ticket
    WORKFLOWS = "steps-index"     # Episodic memory - reuses existing steps-index
    SUCCESS_CASES = "steps-index"  # Reuses steps-index with namespace="success"
    # Sparse indexes for hybrid search (keyword/lexical search)
    STEPS_SPARSE = "steps-sparse"    # Companion sparse index for steps-index
    HAMMER_SPARSE = "hammer-sparse"  # Companion sparse index for hammer-index
    # Deprecated indexes (kept for backwards compatibility)
    JIRA = "jira-index"           # Jira data - deprecated
    ZENDESK = "zendesk-index"     # Zendesk docs - deprecated
    STEPS = "steps-index"         # Legacy alias for WORKFLOWS


# Indexes that reset when testing a new client/ticket
RESETTABLE_INDEXES = [IndexType.HAMMER]

# Indexes that persist forever (episodic memory)
PERSISTENT_INDEXES = [IndexType.WORKFLOWS]


class PineconeService:
    """
    Manages Pinecone indexes with different retention policies.
    
    - hammer-index: Reset when testing new ticket
    - steps-index: Persistent, with intelligent versioning and deduplication
    """

    def __init__(self, api_key: Optional[str] = None, environment: str = "us-east-1"):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.pc = Pinecone(api_key=self.api_key)
        
        # Dimensions per index type - ALL USE GEMINI MRL_DIMENSION for consistency
        self.dimensions = {
            IndexType.HAMMER: MRL_DIMENSION,       # gemini-embedding-001
            IndexType.WORKFLOWS: MRL_DIMENSION,    # gemini-embedding-001
            IndexType.SUCCESS_CASES: MRL_DIMENSION, # gemini-embedding-001
            # Legacy/deprecated indexes (kept at original dims if they exist)
            IndexType.JIRA: 1024,        # deprecated
            IndexType.ZENDESK: 1024,     # deprecated
            IndexType.STEPS: MRL_DIMENSION,        # alias for WORKFLOWS
        }
        self.dimension = MRL_DIMENSION  # Default to Gemini dimension from config
        
        # Only create active indexes (not deprecated ones)
        self._ensure_indexes_exist()

    def _ensure_indexes_exist(self):
        """Create active indexes if they don't exist (skip deprecated)."""
        existing = self.pc.list_indexes().names()
        
        # Only create active indexes, not deprecated ones (SUCCESS_CASES reuses steps-index)
        active_indexes = [IndexType.HAMMER, IndexType.WORKFLOWS]
        
        for index_type in active_indexes:
            if index_type.value not in existing:
                dimension = self.dimensions.get(index_type, self.dimension)
                print(f"Creating index: {index_type.value} (dim={dimension})")
                try:
                    self.pc.create_index(
                        name=index_type.value,
                        dimension=dimension,
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region=self.environment
                        )
                    )
                except Exception as e:
                    print(f"⚠️ Could not create index {index_type.value}: {e}")
                    print(f"   If you hit plan limits, consider deleting unused indexes (jira-index, zendesk-index)")

    def get_index(self, index_type: IndexType):
        """Get a Pinecone index by type."""
        return self.pc.Index(index_type.value)

    # ==================== RESETTABLE INDEXES (hammer, jira, zendesk) ====================

    def reset_for_new_ticket(self, ticket_id: str = None):
        """
        Clear all resettable indexes for a new ticket test.
        Call this when starting to test a new ticket.
        """
        for index_type in RESETTABLE_INDEXES:
            self.clear_index(index_type)
        print(f"Cleared indexes for new ticket: {ticket_id or 'unknown'}")

    def clear_index(self, index_type: IndexType):
        """Clear all vectors from an index."""
        index = self.get_index(index_type)
        # Delete all vectors by deleting all namespaces
        try:
            index.delete(delete_all=True)
        except Exception as e:
            print(f"Error clearing {index_type.value}: {e}")

    def upsert_to_index(
        self,
        index_type: IndexType,
        vectors: List[Dict[str, Any]]
    ):
        """
        Upsert vectors to a specific index.
        
        Args:
            index_type: Which index to upsert to
            vectors: List of dicts with 'id', 'values', 'metadata'
        """
        index = self.get_index(index_type)
        
        # Add timestamp to all metadata
        for v in vectors:
            if 'metadata' not in v:
                v['metadata'] = {}
            v['metadata']['indexed_at'] = datetime.now().isoformat()
        
        index.upsert(vectors=vectors)

    def query_index(
        self,
        index_type: IndexType,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict] = None,
        namespace: str = ""  # Added namespace support
    ) -> List[Dict]:
        """Query an index and return matches."""
        index = self.get_index(index_type)
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter,
            namespace=namespace
        )
        return results.matches

    # ==================== HAMMER INDEX (per-client config) ====================

    def query_hammer(self, query_text: str, top_k: int = 5, use_hybrid: bool = True) -> List[Dict]:
        """
        Query the hammer-index with a text query.
        
        Args:
            query_text: Natural language query about hammer config
            top_k: Number of results to return
            use_hybrid: If True, use hybrid search (semantic + keyword)
            
        Returns:
            List of matching records with metadata
        """
        if use_hybrid:
            return self.query_hammer_hybrid(query_text, top_k)
        
        # Fallback to dense-only search
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        embedding = embedder.embed_query(query_text)
        
        results = self.query_index(IndexType.HAMMER, embedding, top_k)
        
        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            }
            for match in results
        ]
    
    def query_hammer_hybrid(self, query_text: str, top_k: int = 5, alpha: float = 0.5) -> List[Dict]:
        """
        Query hammer-index using HYBRID SEARCH (Semantic + Keyword).
        
        Uses native Pinecone hybrid search with both dense and sparse
        vectors in the SAME index. Combines:
        - Gemini embeddings (semantic understanding)
        - BM25 sparse vectors (exact keyword matching)
        
        Args:
            query_text: Natural language query or exact ID
            top_k: Number of results to return
            alpha: Weight balance (0=all keyword, 1=all semantic, 0.5=balanced)
            
        Returns:
            List of matching records with combined scoring
        """
        try:
            from hybrid_search import get_hybrid_search_service
            
            hybrid_service = get_hybrid_search_service()
            results = hybrid_service.hybrid_search(
                index_name="hammer-index",
                query_text=query_text,
                top_k=top_k,
                alpha=alpha
            )
            
            return [
                {
                    "id": r.id,
                    "score": r.score,
                    "metadata": r.metadata
                }
                for r in results
            ]
        except Exception as e:
            print(f"[HYBRID] Hammer hybrid search failed, falling back to dense: {e}")
            return self.query_hammer(query_text, top_k, use_hybrid=False)
    
    def get_hammer_stats(self) -> Dict:
        """Get stats for the hammer-index."""
        try:
            index = self.get_index(IndexType.HAMMER)
            stats = index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear_hammer_for_new_client(self, client_id: str = None):
        """
        Clear hammer-index for a new client's data.
        
        Note: With native hybrid search, dense and sparse vectors are in the
        same index, so we only need to clear one index.
        
        Args:
            client_id: Optional client ID for logging
        """
        print(f"🧹 Clearing hammer-index for new client: {client_id or 'unknown'}")
        self.clear_index(IndexType.HAMMER)
        print("   ✓ hammer-index cleared (dense + sparse vectors)")


    # ==================== STEPS INDEX (persistent, intelligent) ====================

    def _generate_step_id(self, action_type: str, goal_description: str) -> str:
        """Generate a unique ID for a step based on action and goal."""
        content = f"{action_type}:{goal_description}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def upsert_step(
        self,
        action_type: str,
        goal_description: str,
        step_details: Dict[str, Any],
        embedding: List[float],
        efficiency_score: float = 1.0
    ):
        """
        Upsert a workflow to the persistent steps index.
        
        CLEAN JSON FORMAT - Stores metadata as pure JSON (no formatting):
        - urls_visited: JSON array of unique URLs
        - actions: JSON object of action_type -> count
        - steps: JSON array of step objects (NO coordinates!)
        
        This format saves ~40% tokens compared to human-readable formatting.
        
        Args:
            action_type: Type of action (for ID generation only)
            goal_description: What this step achieves (for ID generation only)
            step_details: Full step data containing 'steps' list
            embedding: Vector embedding of the step
            efficiency_score: Not used, kept for backwards compatibility
        """
        import json
        
        step_id = self._generate_step_id(action_type, goal_description)
        version_id = f"{step_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Extract steps from step_details
        steps = step_details.get("steps", [])
        
        # 1. URLs Visited - list of unique URLs (ordered by visit)
        urls_visited = []
        for step in steps:
            url = step.get("url") if isinstance(step, dict) else getattr(step, "url", None)
            if url and url not in urls_visited:
                urls_visited.append(url)
        
        # 2. Actions Performed - dict of action_type -> count
        actions_performed = {}
        for step in steps:
            action = step.get("action_type") if isinstance(step, dict) else getattr(step, "action_type", "unknown")
            action = action or "unknown"
            actions_performed[action] = actions_performed.get(action, 0) + 1
        
        # 3. Steps Reference Only - clean step details (NO coordinates, NO timestamps!)
        steps_clean = []
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                step_info = {
                    "step": i,
                    "url": step.get("url"),
                    "reasoning": step.get("reasoning")[:300] if step.get("reasoning") else None
                }
            else:
                step_info = {
                    "step": i,
                    "url": getattr(step, "url", None),
                    "reasoning": getattr(step, "reasoning", "")[:300] if getattr(step, "reasoning", None) else None
                }
            # Remove None values for cleaner JSON
            step_info = {k: v for k, v in step_info.items() if v is not None}
            steps_clean.append(step_info)
        
        # ============================================
        # CLEAN JSON METADATA - Pure JSON, no formatting
        # ============================================
        metadata = {
            "urls_visited": json.dumps(urls_visited),
            "actions": json.dumps(actions_performed),
            "steps": json.dumps(steps_clean)[:10000],  # Truncate for Pinecone limits
            "format": "json_v2",  # Flag to identify new format
        }
        
        index = self.get_index(IndexType.STEPS)
        
        index.upsert(vectors=[{
            "id": version_id,
            "values": embedding,
            "metadata": metadata
        }])
        
        return version_id

    def upsert_workflow_record(
        self,
        workflow_id: str,
        name: str,
        description: str,
        embedding: List[float],
        namespace: str = "test_execution_steps",
        index_name: str = "steps-index",
        text: str = "",
        urls_visited: List[str] = None,
        actions_performed: Dict[str, int] = None,
        steps_reference_only: List[Dict] = None,
        tags: List[str] = None,
        extra_metadata: Dict[str, Any] = None,
        user_prompts: List[str] = None
    ) -> str:
        """
        Upsert a workflow record with enhanced metadata for test execution tracking.
        
        This method supports:
        - Custom namespace selection (test_execution_steps, test_success_cases)
        - Custom index selection (steps-index, hammer-index)
        - Structured metadata fields for reference (WITHOUT x,y coordinates)
        
        Args:
            workflow_id: Unique ID for the workflow
            name: Workflow name
            description: Workflow description
            embedding: Vector embedding for semantic search
            namespace: Pinecone namespace (test_execution_steps or test_success_cases)
            index_name: Target index (steps-index or hammer-index)
            text: User goals/prompts concatenated - PRIMARY search field
            urls_visited: List of unique URLs visited during execution
            actions_performed: Dict of action_type -> count
            steps_reference_only: List of steps for REFERENCE ONLY (no coordinates)
            tags: Optional tags
            extra_metadata: Any additional metadata
            user_prompts: List of user prompts/commands sent during session
            
        Returns:
            The vector ID that was created
        """
        import json
        
        # Generate versioned ID
        version_id = f"{workflow_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # ============================================
        # CLEAN JSON METADATA - Pure JSON, no formatting
        # ============================================
        
        # 1. URLs Visited - JSON array
        urls_list = urls_visited or []
        
        # 2. Actions Performed - JSON object
        actions_dict = actions_performed or {}
        
        # 3. Steps - Clean step objects (NO timestamps, NO coordinates!)
        steps_list = steps_reference_only or []
        steps_clean = []
        for step in steps_list:
            step_info = {
                "step": step.get("step", "?"),
                "url": step.get("url"),
                "reasoning": step.get("reasoning", "")[:300] if step.get("reasoning") else None
            }
            # Remove None values for cleaner JSON
            step_info = {k: v for k, v in step_info.items() if v is not None}
            steps_clean.append(step_info)
        
        # 4. User Prompts - JSON array
        prompts_list = user_prompts or []
        
        # Build clean metadata with JSON fields
        metadata = {
            "urls_visited": json.dumps(urls_list),
            "actions": json.dumps(actions_dict),
            "steps": json.dumps(steps_clean)[:10000],  # Truncate for Pinecone limits
            "user_prompts": json.dumps(prompts_list)[:5000],  # Truncate for limits
            "format": "json_v2",  # Flag to identify new format
        }
        
        # Get the target index
        if index_name == "hammer-index":
            index = self.get_index(IndexType.HAMMER)
        else:
            index = self.get_index(IndexType.STEPS)
        
        # Upsert with namespace
        index.upsert(
            vectors=[{
                "id": version_id,
                "values": embedding,
                "metadata": metadata
            }],
            namespace=namespace
        )
        
        print(f"[WORKFLOW] Indexed '{name}' to {index_name}/{namespace} (id: {version_id})")
        return version_id


    def find_similar_steps(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        prefer_recent: bool = True,
        namespace: str = ""
    ) -> List[Dict]:
        """
        Find steps similar to the query.
        
        Args:
            query_embedding: Embedding of the goal/action
            top_k: Number of results
            prefer_recent: If True, sort by date (most recent first)
            namespace: Namespace to search in (e.g., 'test_execution_steps')
        
        Returns:
            List of matching steps with metadata
        """
        matches = self.query_index(
            IndexType.STEPS,
            query_embedding,
            top_k=top_k * 2,  # Get more to filter
            namespace=namespace
        )
        
        # Parse results
        results = []
        for match in matches:
            result = {
                "id": match.id,
                "score": match.score,
                # OLD format fields (for legacy workflows)
                "action_type": match.metadata.get("action_type"),
                "goal_description": match.metadata.get("goal_description"),
                "step_details": match.metadata.get("step_details"),
                "workflow_name": match.metadata.get("workflow_name"),
                "efficiency_score": match.metadata.get("efficiency_score", 1.0),
                "indexed_at": match.metadata.get("indexed_at"),
                "step_group_id": match.metadata.get("step_group_id"),
                # OLD TEXT format fields (legacy human-readable)
                "actions_performed": match.metadata.get("actions_performed"),
                "system_logs": match.metadata.get("system_logs"),
                # NEW JSON format fields (json_v2)
                "urls_visited": match.metadata.get("urls_visited"),
                "actions": match.metadata.get("actions"),
                "steps": match.metadata.get("steps"),
                "user_prompts": match.metadata.get("user_prompts"),
                "format": match.metadata.get("format"),  # "json_v2" for new format
            }
            results.append(result)
        
        if prefer_recent:
            # Sort by date (most recent first), then by efficiency
            results.sort(key=lambda x: (
                x.get("indexed_at", ""),
                -x.get("efficiency_score", 1.0)
            ), reverse=True)
        
        return results[:top_k]

    def get_step_by_id(self, step_id: str) -> Optional[Dict]:
        """
        Fetch a specific step by its ID (or step_group_id).
        
        Args:
            step_id: The ID of the step to fetch
            
        Returns:
            The step dict with metadata, or None if not found
        """
        index = self.get_index(IndexType.STEPS)
        
        # Try fetching directly
        result = index.fetch(ids=[step_id])
        
        if result and result.vectors and step_id in result.vectors:
            match = result.vectors[step_id]
            return {
                "id": match.id,
                "action_type": match.metadata.get("action_type"),
                "goal_description": match.metadata.get("goal_description"),
                "step_details": match.metadata.get("step_details"),
                "workflow_name": match.metadata.get("workflow_name"),
                "efficiency_score": match.metadata.get("efficiency_score", 1.0),
                "indexed_at": match.metadata.get("indexed_at"),
                "text": match.metadata.get("text") or match.metadata.get("step_details"), # Should be in step_details JSON usually, but check text too logic elsewhere handled
                "step_group_id": match.metadata.get("step_group_id")
            }
            
        return None

    def find_step_by_workflow_id(self, workflow_id: str) -> Optional[Dict]:
        """
        Fetch the most recent step version for a given workflow_id using metadata filtering.
        
        Args:
            workflow_id: The 'id' field in the step_details (e.g. 'workflow_hammer_download_...')
            
        Returns:
            The step dict with metadata, or None if not found
        """
        # We need a dummy vector for the query. 
        # Using a zero vector. The steps index might be 1024 (legacy) or 768 (new).
        # We try to use the configured dimension, but handle the case of mismatch.
        
        # Try finding the dimension from stats if possible, or try common sizes.
        # Since we just want metadata filtering, implicit 'id' query is best but we don't have ID.
        
        # HACK: Try 1024 first as that seems to be the configured size per error.
        dim = 1024 
        dummy_vector = [0.0] * dim
        
        try:
            matches = self.query_index(
                IndexType.STEPS,
                query_vector=dummy_vector,
                top_k=1, # We only need the latest one
                filter={"workflow_id": {"$eq": workflow_id}}
            )
        except Exception:
             # Retry with MRL_DIMENSION if 1024 failed
            dim = MRL_DIMENSION
            dummy_vector = [0.0] * dim
            matches = self.query_index(
                IndexType.STEPS,
                query_vector=dummy_vector,
                top_k=1,
                filter={"workflow_id": {"$eq": workflow_id}}
            )

        if matches:

            match = matches[0]
            return {
                "id": match.id,
                "action_type": match.metadata.get("action_type"),
                "goal_description": match.metadata.get("goal_description"),
                "step_details": match.metadata.get("step_details"),
                "workflow_name": match.metadata.get("workflow_name"),
                "efficiency_score": match.metadata.get("efficiency_score", 1.0),
                "indexed_at": match.metadata.get("indexed_at"),
                "text": match.metadata.get("text") or match.metadata.get("step_details"),
                "step_group_id": match.metadata.get("step_group_id")
            }
        
        return None

    def get_best_step_for_goal(
        self,
        query_embedding: List[float],
        similarity_threshold: float = 0.85,
        namespace: str = ""
    ) -> Optional[Dict]:
        """
        Find the best step to achieve a goal.
        
        Strategy:
        1. Find similar steps above threshold
        2. Pick the most recent one with best efficiency
        
        Args:
            query_embedding: Embedding of the goal
            similarity_threshold: Minimum similarity score
            namespace: Namespace to search in
        
        Returns:
            Best matching step or None
        """
        matches = self.find_similar_steps(query_embedding, top_k=10, namespace=namespace)
        
        # Filter by similarity
        good_matches = [m for m in matches if m["score"] >= similarity_threshold]
        
        if not good_matches:
            return None
        
        # Group by step_group_id and pick best from each group
        groups: Dict[str, List[Dict]] = {}
        for match in good_matches:
            group_id = match.get("step_group_id", match["id"])
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(match)
        
        # From each group, pick the most recent with best efficiency
        best_per_group = []
        for group_id, group_matches in groups.items():
            # Sort by efficiency (lower is better), then by date (recent first)
            group_matches.sort(key=lambda x: (
                x.get("efficiency_score", 1.0),
                -datetime.fromisoformat(x.get("indexed_at", "2000-01-01")).timestamp()
            ))
            best_per_group.append(group_matches[0])
        
        # Pick overall best (highest similarity, best efficiency)
        best_per_group.sort(key=lambda x: (
            -x["score"],
            x.get("efficiency_score", 1.0)
        ))
        
        return best_per_group[0] if best_per_group else None

    def get_best_step_for_goal_tiered(
        self,
        query_embedding: List[float],
        keywords: List[str] = None,
        thresholds: List[float] = None,
        namespace: str = ""
    ) -> Optional[Dict]:
        """
        Find the best step using TIERED thresholds and keyword fallback.
        
        This is smarter than get_best_step_for_goal because it:
        1. Tries multiple thresholds (high → low)
        2. Falls back to keyword matching if semantic search fails
        3. Returns the best available match rather than nothing
        
        IMPORTANT: Minimum threshold is 0.15 to filter out irrelevant matches.
        
        Args:
            query_embedding: Embedding of the goal
            keywords: Optional list of keywords for fallback matching
            thresholds: List of thresholds to try (default: [0.35, 0.25, 0.15])
            namespace: Namespace to search in
        
        Returns:
            Best matching step or None
        """
        if thresholds is None:
            # Balanced thresholds: accepts login (~0.15) but rejects irrelevant (~0.07)
            thresholds = [0.35, 0.25, 0.15]
        
        # Get all matches first
        matches = self.find_similar_steps(query_embedding, top_k=20, namespace=namespace)
        
        if not matches:
            print("   No matches found in steps index")
            return None
        
        # Try each threshold tier
        for threshold in thresholds:
            good_matches = [m for m in matches if m["score"] >= threshold]
            
            if good_matches:
                # Found matches at this tier
                best = self._select_best_match(good_matches)
                print(f"   Found match at threshold {threshold}: score={best['score']:.3f}")
                return best
            else:
                print(f"   No matches at threshold {threshold}, trying lower...")
        
        # Keyword fallback: if we have keywords, try to match them
        # Only if semantic score is at least 0.12 (not completely irrelevant)
        if keywords and len(keywords) > 0:
            print(f"   Trying keyword fallback with: {keywords}")
            keyword_matches = self._keyword_match(matches, keywords)
            keyword_matches = [m for m in keyword_matches if m.get("score", 0) >= 0.12]
            if keyword_matches:
                best = self._select_best_match(keyword_matches)
                print(f"   Keyword fallback matched: {best.get('goal_description', 'N/A')} (score: {best['score']:.3f})")
                return best
        
        # REMOVED: No more "last resort" with score > 0.10
        # Anything below 0.15 is likely irrelevant
        print("   No match passed minimum thresholds. Agent will work without workflow guidance.")
        return None
    
    def _select_best_match(self, matches: List[Dict]) -> Dict:
        """Select the best match from a list based on score and recency."""
        if not matches:
            return None
        
        # Group by step_group_id and pick best from each group
        groups: Dict[str, List[Dict]] = {}
        for match in matches:
            group_id = match.get("step_group_id", match["id"])
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(match)
        
        # From each group, pick best
        best_per_group = []
        for group_matches in groups.values():
            group_matches.sort(key=lambda x: (
                -x["score"],
                x.get("efficiency_score", 1.0)
            ))
            best_per_group.append(group_matches[0])
        
        # Pick overall best
        best_per_group.sort(key=lambda x: (-x["score"], x.get("efficiency_score", 1.0)))
        return best_per_group[0]
    
    def _keyword_match(
        self, 
        matches: List[Dict], 
        keywords: List[str],
        min_keyword_matches: int = 1
    ) -> List[Dict]:
        """
        Filter matches by keyword presence in goal_description.
        
        Args:
            matches: List of workflow matches
            keywords: Keywords to look for
            min_keyword_matches: Minimum keywords that must match
        
        Returns:
            Filtered list of matches containing keywords
        """
        keyword_matches = []
        keywords_lower = [k.lower() for k in keywords]
        
        for match in matches:
            goal_desc = match.get("goal_description", "").lower()
            workflow_name = match.get("workflow_name", "").lower()
            combined = f"{goal_desc} {workflow_name}"
            
            # Count keyword matches
            matched_count = sum(1 for kw in keywords_lower if kw in combined)
            
            if matched_count >= min_keyword_matches:
                # Add keyword match score to help with ranking
                match["keyword_match_count"] = matched_count
                keyword_matches.append(match)
        
        # Sort by number of keyword matches, then by original score
        keyword_matches.sort(key=lambda x: (
            -x.get("keyword_match_count", 0),
            -x["score"]
        ))
        
        return keyword_matches

    def get_step_history(self, step_group_id: str) -> List[Dict]:
        """Get all versions of a step by its group ID."""
        index = self.get_index(IndexType.STEPS)
        
        # Query with filter (requires metadata index)
        # For now, we'll use a broad query and filter client-side
        # In production, you'd use metadata filtering
        
        # This is a simplified version - in production use metadata filters
        return []
    
    def find_similar_steps_hybrid(
        self,
        query_text: str,
        top_k: int = 5,
        alpha: float = 0.5,
        keywords: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find similar steps using HYBRID SEARCH (Semantic + Keyword).
        
        Uses native Pinecone hybrid search with both dense and sparse
        vectors in the SAME index.
        
        Args:
            query_text: Natural language query
            top_k: Number of results to return
            alpha: Weight balance (0=all keyword, 1=all semantic, 0.5=balanced)
            keywords: Optional list of keywords to boost in search
            
        Returns:
            List of matching steps with combined scoring
        """
        try:
            from hybrid_search import get_hybrid_search_service
            
            hybrid_service = get_hybrid_search_service()
            
            # Enhance query with keywords if provided
            enhanced_query = query_text
            if keywords:
                enhanced_query = f"{query_text} {' '.join(keywords)}"
            
            results = hybrid_service.hybrid_search(
                index_name="steps-index",
                query_text=enhanced_query,
                top_k=top_k,
                alpha=alpha
            )
            
            # Transform to match existing format
            formatted_results = []
            for r in results:
                metadata = r.metadata or {}
                formatted_results.append({
                    "id": r.id,
                    "score": r.score,
                    "action_type": metadata.get("action_type"),
                    "goal_description": metadata.get("goal_description"),
                    "step_details": metadata.get("step_details"),
                    "workflow_name": metadata.get("workflow_name"),
                    "efficiency_score": metadata.get("efficiency_score", 1.0),
                    "indexed_at": metadata.get("indexed_at"),
                    "step_group_id": metadata.get("step_group_id"),
                })
            
            print(f"[HYBRID] Found {len(formatted_results)} results (alpha={alpha})")
            return formatted_results
            
        except Exception as e:
            print(f"[HYBRID] Search failed, falling back to dense-only: {e}")
            # Fallback to regular dense search
            from screenshot_embedder import get_embedder
            embedder = get_embedder()
            embedding = embedder.embed_query(query_text)
            return self.find_similar_steps(embedding, top_k)

    # ==================== SUCCESS CASES INDEX (reinforcement learning) ====================

    def upsert_success_case(
        self,
        goal_text: str,
        workflow_id: str,
        workflow_name: str,
        steps: List[Dict[str, Any]],
        embedding: List[float],
        final_url: str = "",
        company_context: str = "",
        session_id: str = "",
        execution_time_ms: int = 0
    ) -> str:
        """
        Store a successful workflow execution for future reference.
        
        Args:
            goal_text: The original user prompt/goal
            workflow_id: Reference to the workflow in steps-index
            workflow_name: Human-readable workflow name
            steps: List of actual steps executed
            embedding: 768-dim embedding of the goal text
            final_url: Final URL after execution
            company_context: Company name if applicable (e.g., "FOX", "Linde")
            session_id: Session ID for tracking
            execution_time_ms: Execution duration
        
        Returns:
            The vector ID that was created
        """
        import json
        
        # Generate unique ID
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        vector_id = f"success_{timestamp}_{workflow_id[:8]}"
        
        # Extract step IDs for reference
        step_ids = [str(step.get("step_number", i)) for i, step in enumerate(steps)]
        
        # Serialize steps
        steps_json = json.dumps(steps, ensure_ascii=False, default=str)
        
        metadata = {
            "goal_text": goal_text[:500],  # Truncate for Pinecone limits
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "step_ids": ",".join(step_ids),  # Comma-separated for filtering
            "step_count": len(steps),
            "actual_steps_json": steps_json[:10000],  # Truncate if too long
            "final_url": final_url[:500],
            "company_context": company_context,
            "session_id": session_id,
            "execution_time_ms": execution_time_ms,
            "indexed_at": datetime.now().isoformat(),
            "is_success": True,
        }
        
        index = self.get_index(IndexType.SUCCESS_CASES)
        index.upsert(
            vectors=[{
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            }],
            namespace="success"  # Separate namespace within steps-index
        )
        
        print(f"[SUCCESS] Stored success case: {vector_id} ({workflow_name})")
        return vector_id

    def find_similar_success_cases(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        company_filter: str = None
    ) -> List[Dict]:
        """
        Find successful executions similar to the query.
        
        Args:
            query_embedding: Embedding of the goal
            top_k: Number of results
            company_filter: Optional filter by company context
        
        Returns:
            List of matching success cases with metadata
        """
        filter_dict = None
        if company_filter:
            filter_dict = {"company_context": {"$eq": company_filter}}
        
        # Query with namespace to only get success cases, not workflow steps
        index = self.get_index(IndexType.SUCCESS_CASES)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict,
            namespace="success"  # Only query success cases namespace
        )
        matches = results.matches
        
        results = []
        for match in matches:
            results.append({
                "id": match.id,
                "score": match.score,
                "goal_text": match.metadata.get("goal_text"),
                "workflow_id": match.metadata.get("workflow_id"),
                "workflow_name": match.metadata.get("workflow_name"),
                "step_count": match.metadata.get("step_count"),
                "step_ids": match.metadata.get("step_ids", "").split(","),
                "company_context": match.metadata.get("company_context"),
                "final_url": match.metadata.get("final_url"),
                "indexed_at": match.metadata.get("indexed_at"),
            })
        
        return results

    def get_success_cases_stats(self) -> Dict:
        """Get stats for the success-cases-index."""
        try:
            index = self.get_index(IndexType.SUCCESS_CASES)
            stats = index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
            }
        except Exception as e:
            return {"error": str(e)}

    # ==================== STATIC DATA INDEX (valuable static information) ====================

    # Security patterns to reject (anti-injection)
    DANGEROUS_PATTERNS = [
        r'\$where',      # MongoDB injection
        r'\$gt',         # MongoDB operator
        r'\$ne',         # MongoDB operator
        r'\$regex',      # MongoDB regex
        r'eval\s*\(',    # JS eval
        r'exec\s*\(',    # Python exec
        r'__import__',   # Python import trick
        r'subprocess',   # Command injection
        r'os\.system',   # Command injection
    ]
    
    def _sanitize_static_data(self, data: str) -> str:
        """
        Sanitize user input for static_data namespace.
        
        Security measures:
        1. Strip dangerous HTML/JS tags (but preserve text content)
        2. Limit length to 10,000 chars
        3. Validate no injection patterns
        
        IMPORTANT: Does NOT escape quotes or other valid JSON characters
        to preserve structured data like JSON, credentials, etc.
        
        Args:
            data: Raw user input
            
        Returns:
            Sanitized string safe for storage (preserves JSON structure)
            
        Raises:
            ValueError: If dangerous patterns detected
        """
        import re
        
        # Check for dangerous patterns BEFORE any processing
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, data, re.IGNORECASE):
                raise ValueError(f"Input contains potentially dangerous pattern: {pattern}")
        
        # Strip dangerous HTML/script tags only (preserve content)
        # This removes <script>, <iframe>, <object>, event handlers, etc.
        # but does NOT escape quotes or other valid characters
        dangerous_tags = [
            r'<script[^>]*>.*?</script>',  # Script tags with content
            r'<script[^>]*>',               # Opening script tags
            r'</script>',                   # Closing script tags
            r'<iframe[^>]*>.*?</iframe>',   # Iframes
            r'<iframe[^>]*>',
            r'</iframe>',
            r'<object[^>]*>.*?</object>',   # Objects
            r'<embed[^>]*>',                # Embeds
            r'<link[^>]*>',                 # External links
            r'<style[^>]*>.*?</style>',     # Style tags
            r'on\w+\s*=\s*["\'][^"\']*["\']',  # Event handlers like onclick=""
            r'javascript:',                  # javascript: URLs
            r'data:text/html',               # data URLs with HTML
        ]
        
        sanitized = data
        for pattern in dangerous_tags:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Limit length
        if len(sanitized) > 10000:
            sanitized = sanitized[:10000]
        
        return sanitized.strip()
    
    def upsert_static_data(
        self,
        data: str,
        embedding: List[float]
    ) -> str:
        """
        Store static data in the static_data namespace.
        
        This namespace is for valuable information that rarely changes
        (credentials, API keys, configuration values, reference data).
        
        Args:
            data: User-provided content (will be sanitized)
            embedding: Vector embedding of the data
            
        Returns:
            The vector ID that was created
            
        Raises:
            ValueError: If data contains dangerous patterns
        """
        import json
        
        # SECURITY: Sanitize input
        sanitized_data = self._sanitize_static_data(data)
        
        # Generate unique ID from content hash + timestamp
        content_hash = hashlib.md5(sanitized_data.encode()).hexdigest()[:16]
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        vector_id = f"static_{content_hash}_{timestamp}"
        
        # Build metadata
        metadata = {
            "data": sanitized_data,
            "indexed_at": datetime.now().isoformat(),
            "data_type": "static",
            "char_count": len(sanitized_data),
        }
        
        # Store in steps-index with static_data namespace
        index = self.get_index(IndexType.STEPS)
        index.upsert(
            vectors=[{
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            }],
            namespace="static_data"
        )
        
        print(f"[STATIC] Stored static data (id: {vector_id}, chars: {len(sanitized_data)})")
        return vector_id
    
    def query_static_data(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Query the static_data namespace for relevant records.
        
        Args:
            query_embedding: Vector embedding of the query
            top_k: Number of results to return
            
        Returns:
            List of matching records with metadata
        """
        index = self.get_index(IndexType.STEPS)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace="static_data"
        )
        
        formatted = []
        for match in results.matches:
            formatted.append({
                "id": match.id,
                "score": match.score,
                "data": match.metadata.get("data", ""),
                "indexed_at": match.metadata.get("indexed_at"),
                "char_count": match.metadata.get("char_count", 0),
            })
        
        return formatted
    
    def find_all_static_data(self, limit: int = 20) -> List[Dict]:
        """
        Retrieve all static data records (for agent context building).
        
        Uses a dummy vector query to get all records since Pinecone
        doesn't support list-all operations directly.
        
        Args:
            limit: Max records to return
            
        Returns:
            List of all static data records
        """
        # Use a neutral vector for broad retrieval
        dummy_vector = [0.0] * MRL_DIMENSION
        return self.query_static_data(dummy_vector, top_k=limit)

    # ==================== UTILITY METHODS ====================

    def get_index_stats(self, index_type: IndexType) -> Dict:
        """Get stats for an index."""
        index = self.get_index(index_type)
        return index.describe_index_stats()

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get stats for all indexes."""
        stats = {}
        for index_type in IndexType:
            try:
                stats[index_type.value] = self.get_index_stats(index_type)
            except Exception as e:
                stats[index_type.value] = {"error": str(e)}
        return stats
