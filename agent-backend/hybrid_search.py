"""Hybrid Search Service - Single Index with Dense + Sparse Vectors.

This module implements native Pinecone hybrid search where both dense and sparse
vectors are stored in the SAME index. Only 2 indexes needed:
- steps-index: For workflow/steps search
- hammer-index: For hammer configuration search

Both use:
- Gemini embeddings (768-dim) for semantic/dense search
- Pinecone's pinecone-sparse-english-v0 for keyword/sparse search
- Native alpha-weighted scoring (no RRF needed with single index)
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from pinecone import Pinecone, ServerlessSpec

from config import GOOGLE_API_KEY, PINECONE_API_KEY, MRL_DIMENSION
from screenshot_embedder import get_embedder


@dataclass
class HybridSearchResult:
    """Represents a single hybrid search result."""
    id: str
    score: float  # Combined score from hybrid search
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata
        }


class HybridSearchService:
    """
    Native Hybrid Search using Pinecone's single-index dense+sparse architecture.
    
    Architecture (SIMPLIFIED - Single Index):
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  Upsert: Record → [Dense Embedding] + [Sparse Embedding] → Single Index│
    │                                                                          │
    │  Query:  Query  → [Dense Embedding] + [Sparse Embedding] → Single Index │
    │                            ↓                                             │
    │                   Alpha-Weighted Combined Results                        │
    └─────────────────────────────────────────────────────────────────────────┘
    
    INDEXES (only 2):
    - steps-index: Workflows, success cases, execution steps
    - hammer-index: Hammer configuration data
    
    Both indexes use metric="dotproduct" to support hybrid dense+sparse search.
    """
    
    # Pinecone's sparse embedding model
    SPARSE_MODEL = "pinecone-sparse-english-v0"
    
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
        
    # ==================== INDEX MANAGEMENT ====================
    
    def ensure_hybrid_index_exists(self, index_name: str, dimension: int = MRL_DIMENSION) -> bool:
        """
        Ensure a hybrid index exists with dotproduct metric (required for sparse).
        
        Args:
            index_name: Name of the index (steps-index or hammer-index)
            dimension: Dense vector dimension (768 for Gemini)
            
        Returns:
            True if index exists or was created
        """
        existing = self.pc.list_indexes().names()
        
        if index_name not in existing:
            print(f"[HYBRID] Creating hybrid index: {index_name}")
            try:
                self.pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="dotproduct",  # Required for hybrid dense+sparse
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=self.environment
                    )
                )
                print(f"[HYBRID] Index {index_name} created successfully")
                return True
            except Exception as e:
                print(f"[HYBRID] Could not create index: {e}")
                return False
        
        return True
    
    # ==================== EMBEDDING GENERATION ====================
    
    def generate_dense_embedding(self, text: str) -> List[float]:
        """Generate dense embedding using Gemini."""
        return self.embedder.embed_query(text)
    
    def generate_sparse_embedding(self, text: str, input_type: str = "query") -> Dict[str, Any]:
        """
        Generate sparse embedding using Pinecone's BM25 model.
        
        Args:
            text: Text to convert to sparse vector
            input_type: "query" or "passage"
            
        Returns:
            Dict with 'indices' and 'values' for sparse_values
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
                    "indices": embedding.get("sparse_indices", []),
                    "values": embedding.get("sparse_values", [])
                }
        except Exception as e:
            print(f"[HYBRID] Sparse embedding failed: {e}")
            
        return {"indices": [], "values": []}
    
    # ==================== HYBRID UPSERT (Single Index) ====================
    
    def hybrid_upsert(
        self,
        index_name: str,
        records: List[Dict[str, Any]],
        text_field: str = "searchable_text",
        namespace: str = ""
    ) -> int:
        """
        Upsert records with BOTH dense and sparse vectors to a SINGLE index.
        
        Records must have:
        - 'id': Unique identifier
        - text_field: Text to embed (default: 'searchable_text')
        - 'metadata': Additional metadata (optional)
        - 'dense_embedding': Pre-computed dense embedding (optional)
        
        Args:
            index_name: Target index (steps-index or hammer-index)
            records: List of records to upsert
            text_field: Field containing text to embed
            namespace: Pinecone namespace
            
        Returns:
            Number of records upserted
        """
        if not records:
            return 0
            
        self.ensure_hybrid_index_exists(index_name)
        index = self.pc.Index(index_name)
        
        vectors = []
        
        for record in records:
            record_id = record.get("id")
            text = record.get(text_field, "")
            metadata = record.get("metadata", {})
            
            if not record_id or not text:
                continue
                
            # Add timestamp if not present
            if "indexed_at" not in metadata:
                metadata["indexed_at"] = datetime.now().isoformat()
            
            # Store searchable text in metadata for retrieval
            metadata["searchable_text"] = text[:1000]
            
            # Dense vector (use pre-computed if available)
            dense_embedding = record.get("dense_embedding")
            if not dense_embedding:
                dense_embedding = self.generate_dense_embedding(text)
            
            # Sparse vector
            sparse = self.generate_sparse_embedding(text, input_type="passage")
            
            vector_data = {
                "id": record_id,
                "values": dense_embedding,
                "metadata": metadata
            }
            
            # Add sparse values if available
            if sparse["indices"]:
                vector_data["sparse_values"] = sparse
            
            vectors.append(vector_data)
        
        # Upsert to single index with both dense and sparse
        if vectors:
            try:
                if namespace:
                    index.upsert(vectors=vectors, namespace=namespace)
                else:
                    index.upsert(vectors=vectors)
                print(f"[HYBRID] Upserted {len(vectors)} vectors to {index_name}")
                return len(vectors)
            except Exception as e:
                print(f"[HYBRID] Upsert failed: {e}")
                return 0
        
        return 0
    
    # ==================== HYBRID SEARCH (Single Index) ====================
    
    def hybrid_search(
        self,
        index_name: str,
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.5,
        namespace: str = "",
        filter_dict: Optional[Dict] = None
    ) -> List[HybridSearchResult]:
        """
        Execute hybrid search on a SINGLE index with both dense and sparse.
        
        Args:
            index_name: Target index (steps-index or hammer-index)
            query_text: Natural language query
            top_k: Number of results to return
            alpha: Weight balance (0=all sparse/keyword, 1=all dense/semantic)
            namespace: Pinecone namespace
            filter_dict: Optional metadata filter
            
        Returns:
            List of HybridSearchResult sorted by combined score
        """
        index = self.pc.Index(index_name)
        
        # Generate both embeddings
        dense_embedding = self.generate_dense_embedding(query_text)
        sparse = self.generate_sparse_embedding(query_text, input_type="query")
        
        # Build query params
        query_params = {
            "vector": dense_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        
        # Add sparse vector if available
        if sparse["indices"]:
            query_params["sparse_vector"] = sparse
        
        if namespace:
            query_params["namespace"] = namespace
        if filter_dict:
            query_params["filter"] = filter_dict
            
        try:
            results = index.query(**query_params)
            
            return [
                HybridSearchResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata or {}
                )
                for match in results.matches
            ]
        except Exception as e:
            print(f"[HYBRID] Search failed: {e}")
            # Fallback to dense-only search
            return self._dense_only_search(index, dense_embedding, top_k, namespace, filter_dict)
    
    def _dense_only_search(
        self,
        index,
        dense_embedding: List[float],
        top_k: int,
        namespace: str,
        filter_dict: Optional[Dict]
    ) -> List[HybridSearchResult]:
        """Fallback to dense-only search if hybrid fails."""
        query_params = {
            "vector": dense_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        if namespace:
            query_params["namespace"] = namespace
        if filter_dict:
            query_params["filter"] = filter_dict
            
        results = index.query(**query_params)
        
        return [
            HybridSearchResult(
                id=match.id,
                score=match.score,
                metadata=match.metadata or {}
            )
            for match in results.matches
        ]
    
    # ==================== CONVENIENCE METHODS ====================
    
    def search_steps_hybrid(
        self,
        query_text: str,
        top_k: int = 5,
        namespace: str = ""
    ) -> List[Dict[str, Any]]:
        """Search steps-index using hybrid search."""
        results = self.hybrid_search(
            index_name="steps-index",
            query_text=query_text,
            top_k=top_k,
            namespace=namespace
        )
        return [r.to_dict() for r in results]
    
    def search_hammer_hybrid(
        self,
        query_text: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search hammer-index using hybrid search."""
        results = self.hybrid_search(
            index_name="hammer-index",
            query_text=query_text,
            top_k=top_k
        )
        return [r.to_dict() for r in results]
    
    def get_stats(self, index_name: str) -> Dict[str, Any]:
        """Get stats for an index."""
        try:
            index = self.pc.Index(index_name)
            stats = index.describe_index_stats()
            return {
                "index_name": index_name,
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
            }
        except Exception as e:
            return {"error": str(e)}


# ==================== SINGLETON INSTANCE ====================

_hybrid_service: Optional[HybridSearchService] = None


def get_hybrid_search_service() -> HybridSearchService:
    """Get the singleton HybridSearchService instance."""
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridSearchService()
    return _hybrid_service
