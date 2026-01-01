"""Hybrid Search Service - Combines Semantic (Dense) + Keyword (Sparse) Search.

This module implements a hybrid search architecture using Pinecone's recommended
approach of separate dense and sparse indexes. It uses:
- Gemini embeddings (768-dim) for semantic/dense search
- Pinecone's pinecone-sparse-english-v0 for keyword/sparse search
- Reciprocal Rank Fusion (RRF) for combining results

MIT-quality implementation following best practices for distributed systems.
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from pinecone import Pinecone, ServerlessSpec

from config import GOOGLE_API_KEY, PINECONE_API_KEY
from screenshot_embedder import get_embedder


@dataclass
class HybridSearchResult:
    """Represents a single hybrid search result with combined scoring."""
    id: str
    dense_score: float  # Score from semantic search (0-1)
    sparse_score: float  # Score from keyword search (unbounded)
    rrf_score: float  # Combined RRF score
    dense_rank: int  # Rank in dense results (1-indexed)
    sparse_rank: int  # Rank in sparse results (1-indexed)
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "rrf_score": self.rrf_score,
            "dense_rank": self.dense_rank,
            "sparse_rank": self.sparse_rank,
            "metadata": self.metadata
        }


class HybridSearchService:
    """
    Hybrid Search combining Semantic (Gemini) + Keyword (Pinecone BM25) search.
    
    Architecture:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  Query → [Dense Embedding] → Dense Index → Top-K Dense Results         │
    │       → [Sparse Embedding] → Sparse Index → Top-K Sparse Results       │
    │                                    ↓                                    │
    │                         Merge + Dedupe + RRF Fusion                     │
    │                                    ↓                                    │
    │                         Final Ranked Results                            │
    └─────────────────────────────────────────────────────────────────────────┘
    
    Uses Gemini embeddings for semantic understanding and Pinecone's sparse
    model for exact keyword matching. This hybrid approach handles both:
    - Semantic queries: "login to the system" ≈ "sign in to platform"
    - Keyword queries: "error 401", "ID US12345", "RELS_OPP_CTRL_001"
    """
    
    # Pinecone's sparse embedding model
    SPARSE_MODEL = "pinecone-sparse-english-v0"
    
    # RRF constant (standard value, controls fusion behavior)
    RRF_K = 60
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        environment: str = "us-east-1"
    ):
        """
        Initialize the Hybrid Search Service.
        
        Args:
            api_key: Pinecone API key (uses env var if not provided)
            environment: AWS region for Pinecone indexes
        """
        self.api_key = api_key or PINECONE_API_KEY or os.getenv("PINECONE_API_KEY")
        self.environment = environment
        self.pc = Pinecone(api_key=self.api_key)
        self.embedder = get_embedder()  # Gemini embeddings for dense
        
        # Index name mappings (dense -> sparse companion)
        self.sparse_suffix = "-sparse"
        
    # ==================== INDEX MANAGEMENT ====================
    
    def get_sparse_index_name(self, dense_index_name: str) -> str:
        """Get the companion sparse index name for a dense index."""
        # Remove any existing suffix and add sparse suffix
        base_name = dense_index_name.replace("-index", "").replace(self.sparse_suffix, "")
        return f"{base_name}{self.sparse_suffix}"
    
    def ensure_sparse_index_exists(
        self, 
        dense_index_name: str,
        dimension: int = 768
    ) -> str:
        """
        Create a sparse companion index for a dense index if it doesn't exist.
        
        Args:
            dense_index_name: Name of the existing dense index
            dimension: Not used for sparse, but kept for API consistency
            
        Returns:
            Name of the sparse index
        """
        sparse_name = self.get_sparse_index_name(dense_index_name)
        existing = self.pc.list_indexes().names()
        
        if sparse_name not in existing:
            print(f"[HYBRID] Creating sparse index: {sparse_name}")
            try:
                # Create index with integrated sparse embedding model
                self.pc.create_index_for_model(
                    name=sparse_name,
                    cloud="aws",
                    region=self.environment,
                    embed={
                        "model": self.SPARSE_MODEL,
                        "field_map": {"text": "searchable_text"}
                    }
                )
                print(f"[HYBRID] Sparse index {sparse_name} created successfully")
            except Exception as e:
                # Fallback: create manual sparse index if integrated fails
                print(f"[HYBRID] Integrated sparse index failed, creating manual: {e}")
                self._create_manual_sparse_index(sparse_name)
        else:
            print(f"[HYBRID] Sparse index {sparse_name} already exists")
            
        return sparse_name
    
    def _create_manual_sparse_index(self, sparse_name: str):
        """Fallback: Create sparse index without integrated embedding."""
        try:
            self.pc.create_index(
                name=sparse_name,
                dimension=1,  # Sparse vectors don't need fixed dimension
                metric="dotproduct",  # Required for sparse search
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self.environment
                )
            )
        except Exception as e:
            print(f"[HYBRID] Could not create sparse index: {e}")
            print("   Consider deleting unused indexes to free up space")
    
    # ==================== EMBEDDING GENERATION ====================
    
    def generate_dense_embedding(self, text: str, is_query: bool = True) -> List[float]:
        """
        Generate dense embedding using the same model as the index.
        
        The steps-index uses llama-text-embed-v2 (1024-dim), so we use that
        for consistency. Falls back to Gemini if llama fails.
        
        Args:
            text: Text to embed
            is_query: True for queries, False for documents
            
        Returns:
            1024-dimensional embedding (llama) or 768-dim (Gemini fallback)
        """
        try:
            # Use llama-text-embed-v2 to match steps-index (1024-dim)
            result = self.pc.inference.embed(
                model="llama-text-embed-v2",
                inputs=[text],
                parameters={
                    "input_type": "query" if is_query else "passage",
                    "truncate": "END"
                }
            )
            if result and len(result.data) > 0:
                return result.data[0].values
        except Exception as e:
            print(f"[HYBRID] Llama embedding failed, falling back to Gemini: {e}")
        
        # Fallback to Gemini (768-dim) - may cause dimension mismatch with some indexes
        return self.embedder.embed_query(text)
    
    def generate_sparse_embedding(
        self, 
        text: str, 
        input_type: str = "query"
    ) -> Dict[str, Any]:
        """
        Generate sparse embedding using Pinecone's BM25 model.
        
        Args:
            text: Text to convert to sparse vector
            input_type: "query" or "passage"
            
        Returns:
            Dict with 'sparse_indices' and 'sparse_values'
        """
        try:
            result = self.pc.inference.embed(
                model=self.SPARSE_MODEL,
                inputs=[text],
                parameters={"input_type": input_type, "truncate": "END"}
            )
            
            if result and len(result) > 0:
                embedding = result[0]
                return {
                    "sparse_indices": embedding.get("sparse_indices", []),
                    "sparse_values": embedding.get("sparse_values", [])
                }
        except Exception as e:
            print(f"[HYBRID] Sparse embedding failed: {e}")
            
        # Return empty sparse vector on failure
        return {"sparse_indices": [], "sparse_values": []}
    
    # ==================== HYBRID UPSERT ====================
    
    def hybrid_upsert(
        self,
        dense_index_name: str,
        records: List[Dict[str, Any]],
        text_field: str = "searchable_text",
        namespace: str = ""
    ) -> Tuple[int, int]:
        """
        Upsert records to both dense and sparse indexes.
        
        Records must have:
        - 'id': Unique identifier (links dense and sparse)
        - text_field: Text to embed (default: 'searchable_text')
        - 'metadata': Additional metadata (optional)
        - 'dense_embedding': Pre-computed dense embedding (optional)
        
        Args:
            dense_index_name: Name of the dense index
            records: List of records to upsert
            text_field: Field containing text to embed
            namespace: Pinecone namespace
            
        Returns:
            Tuple of (dense_count, sparse_count) upserted
        """
        if not records:
            return (0, 0)
            
        sparse_index_name = self.ensure_sparse_index_exists(dense_index_name)
        
        dense_index = self.pc.Index(dense_index_name)
        sparse_index = self.pc.Index(sparse_index_name)
        
        dense_vectors = []
        sparse_records = []
        
        for record in records:
            record_id = record.get("id")
            text = record.get(text_field, "")
            metadata = record.get("metadata", {})
            
            if not record_id or not text:
                continue
                
            # Add timestamp if not present
            if "indexed_at" not in metadata:
                metadata["indexed_at"] = datetime.now().isoformat()
            
            # Store searchable text in metadata for later retrieval
            metadata["searchable_text"] = text[:1000]  # Truncate for Pinecone limits
            
            # Dense vector (use pre-computed if available)
            dense_embedding = record.get("dense_embedding")
            if not dense_embedding:
                dense_embedding = self.generate_dense_embedding(text, is_query=False)
            
            dense_vectors.append({
                "id": record_id,
                "values": dense_embedding,
                "metadata": metadata
            })
            
            # Sparse record (for integrated sparse index)
            sparse_records.append({
                "_id": record_id,
                text_field: text,
                **{k: v for k, v in metadata.items() if k != "searchable_text"}
            })
        
        # Upsert to dense index
        dense_count = 0
        try:
            dense_index.upsert(vectors=dense_vectors, namespace=namespace)
            dense_count = len(dense_vectors)
            print(f"[HYBRID] Upserted {dense_count} vectors to dense index")
        except Exception as e:
            print(f"[HYBRID] Dense upsert failed: {e}")
        
        # Upsert to sparse index
        sparse_count = 0
        try:
            sparse_index.upsert_records(namespace or "__default__", sparse_records)
            sparse_count = len(sparse_records)
            print(f"[HYBRID] Upserted {sparse_count} records to sparse index")
        except Exception as e:
            # Fallback: try manual sparse upsert
            print(f"[HYBRID] Integrated sparse upsert failed, trying manual: {e}")
            sparse_count = self._manual_sparse_upsert(
                sparse_index, records, text_field, namespace
            )
        
        return (dense_count, sparse_count)
    
    def _manual_sparse_upsert(
        self,
        sparse_index,
        records: List[Dict[str, Any]],
        text_field: str,
        namespace: str
    ) -> int:
        """Fallback: Manual sparse upsert when integrated model unavailable."""
        vectors = []
        for record in records:
            record_id = record.get("id")
            text = record.get(text_field, "")
            metadata = record.get("metadata", {})
            
            if not record_id or not text:
                continue
                
            # Generate sparse embedding manually
            sparse = self.generate_sparse_embedding(text, input_type="passage")
            
            if sparse["sparse_indices"]:
                vectors.append({
                    "id": record_id,
                    "sparse_values": {
                        "indices": sparse["sparse_indices"],
                        "values": sparse["sparse_values"]
                    },
                    "metadata": {"searchable_text": text[:1000], **metadata}
                })
        
        if vectors:
            try:
                sparse_index.upsert(vectors=vectors, namespace=namespace)
                return len(vectors)
            except Exception as e:
                print(f"[HYBRID] Manual sparse upsert also failed: {e}")
                
        return 0
    
    # ==================== HYBRID SEARCH ====================
    
    def hybrid_search(
        self,
        dense_index_name: str,
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.5,
        namespace: str = "",
        filter_dict: Optional[Dict] = None,
        fetch_multiplier: int = 3
    ) -> List[HybridSearchResult]:
        """
        Execute hybrid search combining semantic and keyword results.
        
        Args:
            dense_index_name: Name of the dense index
            query_text: Natural language query
            top_k: Number of final results to return
            alpha: Weight balance (0=all keyword, 1=all semantic, 0.5=balanced)
            namespace: Pinecone namespace
            filter_dict: Optional metadata filter
            fetch_multiplier: How many more results to fetch for fusion (default: 3x)
            
        Returns:
            List of HybridSearchResult sorted by RRF score (best first)
        """
        sparse_index_name = self.get_sparse_index_name(dense_index_name)
        
        # Over-fetch for better fusion (standard practice)
        fetch_k = top_k * fetch_multiplier
        
        # Query dense index (semantic search)
        dense_results = self._query_dense(
            dense_index_name, query_text, fetch_k, namespace, filter_dict
        )
        
        # Query sparse index (keyword search)
        sparse_results = self._query_sparse(
            sparse_index_name, query_text, fetch_k, namespace, filter_dict
        )
        
        # Merge, dedupe, and apply RRF fusion
        fused_results = self._rrf_fusion(dense_results, sparse_results, alpha)
        
        # Return top_k results
        return fused_results[:top_k]
    
    def _query_dense(
        self,
        index_name: str,
        query_text: str,
        top_k: int,
        namespace: str,
        filter_dict: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Query dense index with Gemini embedding."""
        try:
            index = self.pc.Index(index_name)
            query_embedding = self.generate_dense_embedding(query_text, is_query=True)
            
            query_params = {
                "vector": query_embedding,
                "top_k": top_k,
                "include_metadata": True
            }
            if namespace:
                query_params["namespace"] = namespace
            if filter_dict:
                query_params["filter"] = filter_dict
                
            results = index.query(**query_params)
            
            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata or {}
                }
                for match in results.matches
            ]
        except Exception as e:
            print(f"[HYBRID] Dense query failed: {e}")
            return []
    
    def _query_sparse(
        self,
        index_name: str,
        query_text: str,
        top_k: int,
        namespace: str,
        filter_dict: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Query sparse index with keyword matching."""
        try:
            index = self.pc.Index(index_name)
            
            # Try integrated search first
            try:
                results = index.search(
                    namespace=namespace or "__default__",
                    query={
                        "top_k": top_k,
                        "inputs": {"text": query_text}
                    },
                    fields=["searchable_text"]
                )
                
                return [
                    {
                        "id": hit["_id"],
                        "score": hit["_score"],
                        "metadata": hit.get("fields", {})
                    }
                    for hit in results.get("result", {}).get("hits", [])
                ]
            except Exception:
                # Fallback to manual sparse query
                return self._manual_sparse_query(
                    index, query_text, top_k, namespace, filter_dict
                )
                
        except Exception as e:
            print(f"[HYBRID] Sparse query failed: {e}")
            return []
    
    def _manual_sparse_query(
        self,
        index,
        query_text: str,
        top_k: int,
        namespace: str,
        filter_dict: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Fallback: Manual sparse query with BM25 embedding."""
        sparse = self.generate_sparse_embedding(query_text, input_type="query")
        
        if not sparse["sparse_indices"]:
            return []
            
        query_params = {
            "sparse_vector": {
                "indices": sparse["sparse_indices"],
                "values": sparse["sparse_values"]
            },
            "top_k": top_k,
            "include_metadata": True
        }
        if namespace:
            query_params["namespace"] = namespace
        if filter_dict:
            query_params["filter"] = filter_dict
            
        results = index.query(**query_params)
        
        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata or {}
            }
            for match in results.matches
        ]
    
    def _rrf_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        alpha: float = 0.5
    ) -> List[HybridSearchResult]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine dense and sparse results.
        
        RRF Formula: score = sum(1 / (k + rank))
        Where k is a constant (typically 60) and rank is 1-indexed.
        
        We also apply alpha weighting:
        - final_score = alpha * dense_rrf + (1 - alpha) * sparse_rrf
        
        Args:
            dense_results: Results from semantic search
            sparse_results: Results from keyword search
            alpha: Weight for dense vs sparse (0=all sparse, 1=all dense)
            
        Returns:
            List of HybridSearchResult sorted by RRF score
        """
        # Build rank mappings
        dense_ranks = {r["id"]: i + 1 for i, r in enumerate(dense_results)}
        sparse_ranks = {r["id"]: i + 1 for i, r in enumerate(sparse_results)}
        
        # Build score mappings
        dense_scores = {r["id"]: r["score"] for r in dense_results}
        sparse_scores = {r["id"]: r["score"] for r in sparse_results}
        
        # Build metadata mapping (prefer dense metadata)
        all_metadata = {}
        for r in sparse_results:
            all_metadata[r["id"]] = r.get("metadata", {})
        for r in dense_results:
            all_metadata[r["id"]] = r.get("metadata", {})
        
        # Get all unique IDs
        all_ids = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        
        # Calculate RRF scores
        results = []
        max_rank = max(len(dense_results), len(sparse_results)) + 1
        
        for id_ in all_ids:
            dense_rank = dense_ranks.get(id_, max_rank)
            sparse_rank = sparse_ranks.get(id_, max_rank)
            
            # RRF formula
            dense_rrf = 1.0 / (self.RRF_K + dense_rank)
            sparse_rrf = 1.0 / (self.RRF_K + sparse_rank)
            
            # Weighted combination
            rrf_score = alpha * dense_rrf + (1 - alpha) * sparse_rrf
            
            results.append(HybridSearchResult(
                id=id_,
                dense_score=dense_scores.get(id_, 0.0),
                sparse_score=sparse_scores.get(id_, 0.0),
                rrf_score=rrf_score,
                dense_rank=dense_rank,
                sparse_rank=sparse_rank,
                metadata=all_metadata.get(id_, {})
            ))
        
        # Sort by RRF score (descending)
        results.sort(key=lambda x: x.rrf_score, reverse=True)
        
        return results
    
    # ==================== CONVENIENCE METHODS ====================
    
    def search_workflows_hybrid(
        self,
        query_text: str,
        top_k: int = 5,
        alpha: float = 0.5,
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for workflows using hybrid search.
        
        Convenience method that wraps hybrid_search for the steps-index.
        
        Args:
            query_text: Natural language query
            top_k: Number of results
            alpha: Weight balance (default: 0.5 balanced)
            keywords: Optional list of keywords to boost in search
            
        Returns:
            List of workflow matches with combined scoring
        """
        # Enhance query with keywords if provided
        enhanced_query = query_text
        if keywords:
            enhanced_query = f"{query_text} {' '.join(keywords)}"
        
        results = self.hybrid_search(
            dense_index_name="steps-index",
            query_text=enhanced_query,
            top_k=top_k,
            alpha=alpha
        )
        
        return [r.to_dict() for r in results]
    
    def get_stats(self, dense_index_name: str) -> Dict[str, Any]:
        """Get stats for both dense and sparse indexes."""
        sparse_index_name = self.get_sparse_index_name(dense_index_name)
        
        stats = {
            "dense_index": dense_index_name,
            "sparse_index": sparse_index_name
        }
        
        try:
            dense_index = self.pc.Index(dense_index_name)
            dense_stats = dense_index.describe_index_stats()
            stats["dense_vector_count"] = dense_stats.total_vector_count
            stats["dense_dimension"] = dense_stats.dimension
        except Exception as e:
            stats["dense_error"] = str(e)
            
        try:
            sparse_index = self.pc.Index(sparse_index_name)
            sparse_stats = sparse_index.describe_index_stats()
            stats["sparse_vector_count"] = sparse_stats.total_vector_count
        except Exception as e:
            stats["sparse_error"] = str(e)
            
        return stats


# ==================== SINGLETON INSTANCE ====================

_hybrid_service: Optional[HybridSearchService] = None


def get_hybrid_search_service() -> HybridSearchService:
    """Get the singleton HybridSearchService instance."""
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridSearchService()
    return _hybrid_service
