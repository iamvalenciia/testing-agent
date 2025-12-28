"""Pinecone service for managing multiple indexes with different retention policies."""
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from pinecone import Pinecone, ServerlessSpec


class IndexType(str, Enum):
    """Types of Pinecone indexes with different retention policies."""
    HAMMER = "hammer-index"       # Hammer config - resets per ticket
    JIRA = "jira-index"           # Jira data - resets per ticket
    ZENDESK = "zendesk-index"     # Zendesk docs - resets per ticket
    STEPS = "steps-index"         # Agent steps - persistent forever
    SCREENSHOTS = "screenshots-index"  # Visual search - persistent forever


# Indexes that reset when testing a new ticket
RESETTABLE_INDEXES = [IndexType.HAMMER, IndexType.JIRA, IndexType.ZENDESK]

# Indexes that persist forever
PERSISTENT_INDEXES = [IndexType.STEPS, IndexType.SCREENSHOTS]


class PineconeService:
    """
    Manages 4 Pinecone indexes with different retention policies.
    
    - hammer-index, jira-index, zendesk-index: Reset when testing new ticket
    - steps-index: Persistent, with intelligent versioning and deduplication
    """

    def __init__(self, api_key: Optional[str] = None, environment: str = "us-east-1"):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.pc = Pinecone(api_key=self.api_key)
        
        # Dimensions per index type
        self.dimensions = {
            IndexType.HAMMER: 1024,      # llama-text-embed-v2
            IndexType.JIRA: 1024,        # llama-text-embed-v2
            IndexType.ZENDESK: 1024,     # llama-text-embed-v2
            IndexType.STEPS: 1024,       # llama-text-embed-v2
            IndexType.SCREENSHOTS: 768,  # gemini-embedding-001
        }
        self.dimension = 1024  # Default for backwards compatibility
        
        # Ensure all indexes exist
        self._ensure_indexes_exist()

    def _ensure_indexes_exist(self):
        """Create indexes if they don't exist."""
        existing = self.pc.list_indexes().names()
        
        for index_type in IndexType:
            if index_type.value not in existing:
                dimension = self.dimensions.get(index_type, self.dimension)
                print(f"Creating index: {index_type.value} (dim={dimension})")
                self.pc.create_index(
                    name=index_type.value,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.environment
                    )
                )

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
        filter: Optional[Dict] = None
    ) -> List[Dict]:
        """Query an index and return matches."""
        index = self.get_index(index_type)
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter
        )
        return results.matches

    # ==================== HAMMER INDEX (per-client config) ====================

    def query_hammer(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        Query the hammer-index with a text query.
        
        Args:
            query_text: Natural language query about hammer config
            top_k: Number of results to return
            
        Returns:
            List of matching records with metadata
        """
        # Generate embedding for query
        embedding = self.pc.inference.embed(
            model="llama-text-embed-v2",
            inputs=[query_text],
            parameters={"input_type": "query"}
        ).data[0].values
        
        # Query hammer-index
        results = self.query_index(IndexType.HAMMER, embedding, top_k)
        
        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            }
            for match in results
        ]
    
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
        
        Args:
            client_id: Optional client ID for logging
        """
        print(f"🧹 Clearing hammer-index for new client: {client_id or 'unknown'}")
        self.clear_index(IndexType.HAMMER)
        print("   ✓ hammer-index cleared")

    # ==================== SCREENSHOTS INDEX (multimodal visual search) ====================

    def upsert_screenshot(
        self,
        workflow_id: str,
        step_number: int,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Upsert a screenshot embedding to the visual search index.
        
        Args:
            workflow_id: ID of the workflow this screenshot belongs to
            step_number: Step number in the workflow
            embedding: 768-dim embedding from gemini-embedding-001
            metadata: Additional metadata (screenshot_path, action_type, url, etc.)
        
        Returns:
            The vector ID that was created
        """
        vector_id = f"{workflow_id}_step_{step_number}"
        
        # Add required metadata
        full_metadata = {
            **metadata,
            "workflow_id": workflow_id,
            "step_number": step_number,
            "indexed_at": datetime.now().isoformat(),
        }
        
        index = self.get_index(IndexType.SCREENSHOTS)
        index.upsert(vectors=[{
            "id": vector_id,
            "values": embedding,
            "metadata": full_metadata
        }])
        
        print(f"📸 Screenshot indexed: {vector_id}")
        return vector_id

    def find_similar_screenshots(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Find screenshots visually similar to the query.
        
        Args:
            query_embedding: 768-dim embedding (from image or text query)
            top_k: Number of results to return
            filter: Optional metadata filter
        
        Returns:
            List of matching screenshots with metadata
        """
        matches = self.query_index(
            IndexType.SCREENSHOTS,
            query_embedding,
            top_k=top_k,
            filter=filter
        )
        
        results = []
        for match in matches:
            results.append({
                "id": match.id,
                "score": match.score,
                "workflow_id": match.metadata.get("workflow_id"),
                "step_number": match.metadata.get("step_number"),
                "screenshot_path": match.metadata.get("screenshot_path"),
                "action_type": match.metadata.get("action_type"),
                "url": match.metadata.get("url"),
                "workflow_name": match.metadata.get("workflow_name"),
                "indexed_at": match.metadata.get("indexed_at"),
            })
        
        return results

    def find_screen_by_text(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        Search for screenshots using natural language description.
        
        This is a convenience method that generates an embedding from text
        and searches the screenshots index.
        
        Args:
            query_text: Natural language description (e.g., "login page with error")
            top_k: Number of results
        
        Returns:
            List of matching screenshots
        """
        # Import here to avoid circular dependency
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        
        query_embedding = embedder.embed_query(query_text)
        return self.find_similar_screenshots(query_embedding, top_k)

    def get_screenshots_stats(self) -> Dict:
        """Get stats for the screenshots-index."""
        try:
            index = self.get_index(IndexType.SCREENSHOTS)
            stats = index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
            }
        except Exception as e:
            return {"error": str(e)}

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
        Upsert a step to the persistent steps index.
        
        Steps are versioned with timestamps so the agent can:
        - Find similar steps
        - Compare efficiency
        - Choose the most recent/efficient approach
        
        Args:
            action_type: Type of action (e.g., "login", "create_supplier")
            goal_description: What this step achieves
            step_details: Full step data (args, screenshots, etc.)
            embedding: Vector embedding of the step
            efficiency_score: How efficient this step is (1.0 = normal, lower = better)
        """
        import json
        
        step_id = self._generate_step_id(action_type, goal_description)
        version_id = f"{step_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Serialize step_details as JSON string for better reconstruction
        step_details_json = json.dumps(step_details, ensure_ascii=False)
        
        metadata = {
            "action_type": action_type,
            "goal_description": goal_description,
            "step_details": step_details_json,  # JSON string for better parsing
            "efficiency_score": efficiency_score,
            "indexed_at": datetime.now().isoformat(),
            "step_group_id": step_id,  # Groups similar steps together
            "is_current": True,  # Mark as current version
            # Additional searchable fields
            "workflow_id": step_details.get("id", ""),
            "workflow_name": step_details.get("name", ""),
        }
        
        index = self.get_index(IndexType.STEPS)
        
        # Mark previous versions as not current
        # (Pinecone doesn't support updates, so we track via metadata)
        
        index.upsert(vectors=[{
            "id": version_id,
            "values": embedding,
            "metadata": metadata
        }])
        
        return version_id

    def find_similar_steps(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        prefer_recent: bool = True
    ) -> List[Dict]:
        """
        Find steps similar to the query.
        
        Args:
            query_embedding: Embedding of the goal/action
            top_k: Number of results
            prefer_recent: If True, sort by date (most recent first)
        
        Returns:
            List of matching steps with metadata
        """
        matches = self.query_index(
            IndexType.STEPS,
            query_embedding,
            top_k=top_k * 2  # Get more to filter
        )
        
        # Parse results
        results = []
        for match in matches:
            result = {
                "id": match.id,
                "score": match.score,
                "action_type": match.metadata.get("action_type"),
                "goal_description": match.metadata.get("goal_description"),
                "step_details": match.metadata.get("step_details"),
                "workflow_name": match.metadata.get("workflow_name"),
                "efficiency_score": match.metadata.get("efficiency_score", 1.0),
                "indexed_at": match.metadata.get("indexed_at"),
                "step_group_id": match.metadata.get("step_group_id")
            }
            results.append(result)
        
        if prefer_recent:
            # Sort by date (most recent first), then by efficiency
            results.sort(key=lambda x: (
                x.get("indexed_at", ""),
                -x.get("efficiency_score", 1.0)
            ), reverse=True)
        
        return results[:top_k]

    def get_best_step_for_goal(
        self,
        query_embedding: List[float],
        similarity_threshold: float = 0.85
    ) -> Optional[Dict]:
        """
        Find the best step to achieve a goal.
        
        Strategy:
        1. Find similar steps above threshold
        2. Pick the most recent one with best efficiency
        
        Args:
            query_embedding: Embedding of the goal
            similarity_threshold: Minimum similarity score
        
        Returns:
            Best matching step or None
        """
        matches = self.find_similar_steps(query_embedding, top_k=10)
        
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
        thresholds: List[float] = None
    ) -> Optional[Dict]:
        """
        Find the best step using TIERED thresholds and keyword fallback.
        
        This is smarter than get_best_step_for_goal because it:
        1. Tries multiple thresholds (high → low)
        2. Falls back to keyword matching if semantic search fails
        3. Returns the best available match rather than nothing
        
        Args:
            query_embedding: Embedding of the goal
            keywords: Optional list of keywords for fallback matching
            thresholds: List of thresholds to try (default: [0.50, 0.35, 0.20])
        
        Returns:
            Best matching step or None
        """
        if thresholds is None:
            thresholds = [0.50, 0.35, 0.20]
        
        # Get all matches first
        matches = self.find_similar_steps(query_embedding, top_k=20)
        
        if not matches:
            print("   📭 No matches found in steps index")
            return None
        
        # Try each threshold tier
        for threshold in thresholds:
            good_matches = [m for m in matches if m["score"] >= threshold]
            
            if good_matches:
                # Found matches at this tier
                best = self._select_best_match(good_matches)
                print(f"   🎯 Found match at threshold {threshold}: score={best['score']:.3f}")
                return best
            else:
                print(f"   ⏩ No matches at threshold {threshold}, trying lower...")
        
        # Keyword fallback: if we have keywords, try to match them against goal_description
        if keywords and len(keywords) > 0:
            print(f"   🔤 Trying keyword fallback with: {keywords}")
            keyword_matches = self._keyword_match(matches, keywords)
            if keyword_matches:
                best = self._select_best_match(keyword_matches)
                print(f"   ✅ Keyword fallback matched: {best.get('goal_description', 'N/A')}")
                return best
        
        # Last resort: return the top match if score > 0.10 (very permissive)
        if matches and matches[0]["score"] > 0.10:
            print(f"   ⚠️ Using low-confidence match: score={matches[0]['score']:.3f}")
            return matches[0]
        
        print("   ❌ No suitable match found even with fallbacks")
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
