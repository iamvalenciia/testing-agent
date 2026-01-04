"""Tests for Hybrid Search functionality.

Tests the HybridSearchService combining Semantic (Gemini) + Keyword (BM25) search.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from hybrid_search import HybridSearchService, HybridSearchResult, get_hybrid_search_service
from config import MRL_DIMENSION


class TestHybridSearchResult:
    """Tests for HybridSearchResult dataclass."""
    
    def test_creation(self):
        """Test creating a HybridSearchResult."""
        result = HybridSearchResult(
            id="test_001",
            dense_score=0.85,
            sparse_score=12.5,
            rrf_score=0.0156,
            dense_rank=1,
            sparse_rank=3,
            metadata={"goal_description": "login to system"}
        )
        
        assert result.id == "test_001"
        assert result.dense_score == 0.85
        assert result.sparse_score == 12.5
        assert result.dense_rank == 1
        assert result.sparse_rank == 3
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = HybridSearchResult(
            id="test_002",
            dense_score=0.75,
            sparse_score=8.0,
            rrf_score=0.012,
            dense_rank=2,
            sparse_rank=1,
            metadata={"workflow_name": "Login Flow"}
        )
        
        d = result.to_dict()
        
        assert d["id"] == "test_002"
        assert d["dense_score"] == 0.75
        assert d["metadata"]["workflow_name"] == "Login Flow"


class TestRRFFusion:
    """Tests for RRF fusion scoring."""
    
    @patch('hybrid_search.PINECONE_API_KEY', 'test-api-key')
    @patch('hybrid_search.get_embedder')
    @patch('hybrid_search.Pinecone')
    def test_rrf_fusion_basic(self, mock_pinecone, mock_get_embedder):
        """Test basic RRF fusion calculation."""
        mock_embedder = Mock()
        mock_embedder.embed_query.return_value = [0.1] * MRL_DIMENSION
        mock_get_embedder.return_value = mock_embedder
        
        service = HybridSearchService(api_key="test-key")
        
        # Mock dense and sparse results
        dense_results = [
            {"id": "doc1", "score": 0.95, "metadata": {"text": "A"}},
            {"id": "doc2", "score": 0.85, "metadata": {"text": "B"}},
            {"id": "doc3", "score": 0.75, "metadata": {"text": "C"}},
        ]
        
        sparse_results = [
            {"id": "doc2", "score": 15.0, "metadata": {"text": "B"}},
            {"id": "doc4", "score": 12.0, "metadata": {"text": "D"}},
            {"id": "doc1", "score": 8.0, "metadata": {"text": "A"}},
        ]
        
        # Perform fusion with balanced weights
        results = service._rrf_fusion(dense_results, sparse_results, alpha=0.5)
        
        # doc1 appears in both: dense_rank=1, sparse_rank=3
        # doc2 appears in both: dense_rank=2, sparse_rank=1
        # doc3 appears only in dense: dense_rank=3, sparse_rank=max
        # doc4 appears only in sparse: dense_rank=max, sparse_rank=2
        
        assert len(results) == 4
        assert all(isinstance(r, HybridSearchResult) for r in results)
        
        # doc2 should rank high (good in both)
        doc2_result = next(r for r in results if r.id == "doc2")
        assert doc2_result.dense_rank == 2
        assert doc2_result.sparse_rank == 1
    
    @patch('hybrid_search.PINECONE_API_KEY', 'test-api-key')
    @patch('hybrid_search.get_embedder')
    @patch('hybrid_search.Pinecone')
    def test_rrf_fusion_alpha_extremes(self, mock_pinecone, mock_get_embedder):
        """Test RRF fusion with alpha at extremes (0 and 1)."""
        mock_embedder = Mock()
        mock_embedder.embed_query.return_value = [0.1] * MRL_DIMENSION
        mock_get_embedder.return_value = mock_embedder
        
        service = HybridSearchService(api_key="test-key")
        
        dense_results = [
            {"id": "dense_top", "score": 0.99, "metadata": {}},
        ]
        
        sparse_results = [
            {"id": "sparse_top", "score": 20.0, "metadata": {}},
        ]
        
        # Alpha = 1.0: All semantic (dense should win)
        results_dense = service._rrf_fusion(dense_results, sparse_results, alpha=1.0)
        assert results_dense[0].id == "dense_top"
        
        # Alpha = 0.0: All keyword (sparse should win)
        results_sparse = service._rrf_fusion(dense_results, sparse_results, alpha=0.0)
        assert results_sparse[0].id == "sparse_top"


class TestHybridSearchService:
    """Tests for HybridSearchService class."""
    
    @patch('hybrid_search.PINECONE_API_KEY', 'test-api-key')
    @patch('hybrid_search.get_embedder')
    @patch('hybrid_search.Pinecone')
    def test_get_sparse_index_name(self, mock_pinecone, mock_get_embedder):
        """Test sparse index name generation."""
        mock_embedder = Mock()
        mock_get_embedder.return_value = mock_embedder
        
        service = HybridSearchService(api_key="test-key")
        
        assert service.get_sparse_index_name("steps-index") == "steps-sparse"
        assert service.get_sparse_index_name("workflows-index") == "workflows-sparse"
        assert service.get_sparse_index_name("hammer-index") == "hammer-sparse"
    
    @patch('hybrid_search.PINECONE_API_KEY', 'test-api-key')
    @patch('hybrid_search.get_embedder')
    @patch('hybrid_search.Pinecone')
    def test_generate_dense_embedding(self, mock_pinecone, mock_get_embedder):
        """Test dense embedding generation using Gemini."""
        mock_embedder = Mock()
        expected_embedding = [0.1, 0.2, 0.3] + [0.0] * (MRL_DIMENSION - 3)
        mock_embedder.embed_query.return_value = expected_embedding
        mock_get_embedder.return_value = mock_embedder
        
        service = HybridSearchService(api_key="test-key")
        
        result = service.generate_dense_embedding("test query")
        
        assert result == expected_embedding
        mock_embedder.embed_query.assert_called_once_with("test query")


class TestSingleton:
    """Tests for singleton pattern."""
    
    @patch('hybrid_search.PINECONE_API_KEY', 'test-api-key')
    @patch('hybrid_search.get_embedder')
    @patch('hybrid_search.Pinecone')
    def test_singleton_returns_same_instance(self, mock_pinecone, mock_get_embedder):
        """Test that get_hybrid_search_service returns the same instance."""
        mock_embedder = Mock()
        mock_get_embedder.return_value = mock_embedder
        
        # Reset singleton for test
        import hybrid_search
        hybrid_search._hybrid_service = None
        
        service1 = get_hybrid_search_service()
        service2 = get_hybrid_search_service()
        
        assert service1 is service2


class TestIntegration:
    """Integration tests (require actual Pinecone connection)."""
    
    @pytest.mark.skip(reason="Requires actual Pinecone API key")
    def test_full_hybrid_search_flow(self):
        """
        Full integration test:
        1. Create sparse index
        2. Upsert records to both indexes
        3. Perform hybrid search
        4. Verify results contain expected matches
        """
        service = HybridSearchService()
        
        # Test records
        records = [
            {
                "id": "test_login_001",
                "searchable_text": "Login to graphite connect test environment",
                "metadata": {"action_type": "login", "workflow_name": "Login Flow"}
            },
            {
                "id": "test_download_001", 
                "searchable_text": "Download hammer file from Western company",
                "metadata": {"action_type": "download", "workflow_name": "Hammer Download"}
            },
            {
                "id": "test_error_001",
                "searchable_text": "Handle error 401 unauthorized on admin page",
                "metadata": {"action_type": "error_handling", "workflow_name": "Error Recovery"}
            }
        ]
        
        # Upsert
        dense_count, sparse_count = service.hybrid_upsert(
            dense_index_name="steps-index",
            records=records
        )
        
        assert dense_count == 3
        assert sparse_count == 3
        
        # Search - semantic query
        results = service.hybrid_search(
            dense_index_name="steps-index",
            query_text="sign in to the system",
            top_k=3,
            alpha=0.7  # Favor semantic
        )
        
        # Should find login workflow via semantic similarity
        assert len(results) > 0
        assert any(r.id == "test_login_001" for r in results)
        
        # Search - keyword query
        results = service.hybrid_search(
            dense_index_name="steps-index",
            query_text="error 401 admin",
            top_k=3,
            alpha=0.3  # Favor keyword
        )
        
        # Should find error workflow via exact keyword match
        assert len(results) > 0
        assert any(r.id == "test_error_001" for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
