"""Tests for the screenshot embedder service."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent-backend"))


class TestScreenshotEmbedder:
    """Test cases for the ScreenshotEmbedder class."""
    
    @pytest.fixture
    def mock_genai_client(self):
        """Mock the Google GenAI client."""
        with patch("screenshot_embedder.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            
            # Mock embedding response
            mock_embedding = MagicMock()
            mock_embedding.values = [0.1] * 768  # 768-dim embedding
            
            mock_response = MagicMock()
            mock_response.embeddings = [mock_embedding]
            
            mock_client.models.embed_content.return_value = mock_response
            
            yield mock_client
    
    @pytest.fixture
    def embedder(self, mock_genai_client):
        """Create embedder with mocked client."""
        from screenshot_embedder import ScreenshotEmbedder
        return ScreenshotEmbedder()
    
    @pytest.fixture
    def sample_image_path(self, tmp_path):
        """Create a sample PNG file for testing."""
        # Create a minimal PNG file (1x1 white pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D,  # IHDR length
            0x49, 0x48, 0x44, 0x52,  # IHDR chunk type
            0x00, 0x00, 0x00, 0x01,  # width = 1
            0x00, 0x00, 0x00, 0x01,  # height = 1
            0x08, 0x02,  # bit depth = 8, color type = 2 (RGB)
            0x00, 0x00, 0x00,  # compression, filter, interlace
            0x90, 0x77, 0x53, 0xDE,  # CRC
            0x00, 0x00, 0x00, 0x0C,  # IDAT length
            0x49, 0x44, 0x41, 0x54,  # IDAT chunk type
            0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF, 0x00,  # compressed data
            0x05, 0xFE, 0x02, 0xFE,  # CRC
            0x00, 0x00, 0x00, 0x00,  # IEND length
            0x49, 0x45, 0x4E, 0x44,  # IEND chunk type
            0xAE, 0x42, 0x60, 0x82,  # CRC
        ])
        
        image_path = tmp_path / "test_screenshot.png"
        image_path.write_bytes(png_data)
        return str(image_path)
    
    def test_embed_single_image(self, embedder, sample_image_path, mock_genai_client):
        """Test embedding a single screenshot."""
        embedding = embedder.embed_image(sample_image_path)
        
        # Verify embedding dimension
        assert len(embedding) == 768
        
        # Verify API was called
        mock_genai_client.models.embed_content.assert_called_once()
    
    def test_embed_returns_correct_dimension(self, embedder, sample_image_path):
        """Test that embeddings are always 768-dimensional."""
        embedding = embedder.embed_image(sample_image_path)
        assert len(embedding) == 768
    
    def test_embed_with_context(self, embedder, sample_image_path, mock_genai_client):
        """Test embedding with additional context."""
        context = "Login page with email field visible"
        embedding = embedder.embed_image(sample_image_path, include_context=context)
        
        assert len(embedding) == 768
        mock_genai_client.models.embed_content.assert_called_once()
    
    def test_embed_query(self, embedder, mock_genai_client):
        """Test text query embedding."""
        embedding = embedder.embed_query("login page with error message")
        
        assert len(embedding) == 768
        mock_genai_client.models.embed_content.assert_called_once()
    
    def test_embed_batch(self, embedder, sample_image_path, mock_genai_client):
        """Test batch embedding of multiple images."""
        paths = [sample_image_path, sample_image_path]
        embeddings = embedder.embed_image_batch(paths)
        
        assert len(embeddings) == 2
        assert all(len(e) == 768 for e in embeddings)
    
    def test_embed_missing_file_raises_error(self, embedder):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            embedder.embed_image("nonexistent.png")
    
    def test_compute_similarity(self, embedder):
        """Test cosine similarity computation."""
        # Identical vectors should have similarity ~1
        vec = [1.0] * 768
        sim = embedder.compute_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.001
        
        # Orthogonal vectors should have similarity ~0
        vec1 = [1.0] + [0.0] * 767
        vec2 = [0.0] + [1.0] + [0.0] * 766
        sim = embedder.compute_similarity(vec1, vec2)
        assert abs(sim) < 0.001
    
    def test_normalize_embedding(self, embedder):
        """Test that embeddings are normalized to unit length."""
        import numpy as np
        
        # Raw embedding
        raw = [2.0] * 768
        normalized = embedder._normalize_embedding(raw)
        
        # Compute norm of normalized embedding
        norm = np.linalg.norm(np.array(normalized))
        assert abs(norm - 1.0) < 0.001


class TestPineconeScreenshotMethods:
    """Test screenshot methods in PineconeService."""
    
    @pytest.fixture
    def mock_pinecone_service(self):
        """Create a mock PineconeService."""
        with patch("pinecone_service.Pinecone") as mock_pc:
            mock_index = MagicMock()
            mock_pc.return_value.Index.return_value = mock_index
            mock_pc.return_value.list_indexes.return_value.names.return_value = [
                "hammer-index", "jira-index", "zendesk-index", "steps-index", "screenshots-index"
            ]
            
            from pinecone_service import PineconeService
            service = PineconeService(api_key="test-key")
            
            yield service, mock_index
    
    def test_upsert_screenshot(self, mock_pinecone_service):
        """Test upserting a screenshot embedding."""
        service, mock_index = mock_pinecone_service
        
        embedding = [0.1] * 768
        vector_id = service.upsert_screenshot(
            workflow_id="test-workflow",
            step_number=1,
            embedding=embedding,
            metadata={"action_type": "click_at", "url": "https://example.com"}
        )
        
        assert vector_id == "test-workflow_step_1"
        mock_index.upsert.assert_called_once()
    
    def test_screenshots_index_dimension(self, mock_pinecone_service):
        """Test that screenshots index uses 768 dimensions."""
        service, _ = mock_pinecone_service
        
        from pinecone_service import IndexType
        assert service.dimensions[IndexType.SCREENSHOTS] == 768


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
