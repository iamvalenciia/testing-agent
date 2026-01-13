import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock modules BEFORE importing the code under test
mock_pinecone = MagicMock()
sys.modules["pinecone"] = mock_pinecone
mock_google = MagicMock()
sys.modules["google"] = mock_google
mock_genai = MagicMock()
sys.modules["google.genai"] = mock_genai
mock_types = MagicMock()
sys.modules["google.genai.types"] = mock_types

import numpy as np
# Config is imported in vector_store, so we'll patch it where it is used or patch the class attributes

from src.database.vector_store import PineconeService

class TestVectorStore(unittest.TestCase):
    def setUp(self):
        # Reset global mocks to ensure isolation
        mock_types.reset_mock()
        mock_genai.reset_mock()
        mock_pinecone.reset_mock()
        mock_google.reset_mock()

    @patch('src.database.vector_store.Config')
    @patch('src.database.vector_store.Pinecone')
    @patch('src.database.vector_store.genai.Client')
    def test_pinecone_service_initialization(self, mock_client_cls, mock_pinecone_cls, mock_config_cls):
        # Setup Config mock
        mock_config_cls.PINECONE_API_KEY = 'mock_key'
        mock_config_cls.GOOGLE_API_KEY = 'mock_key'
        mock_config_cls.PINECONE_INDEX_NAME = 'hammer-index'
        
        # Setup other mocks
        mock_pc_instance = MagicMock()
        mock_pinecone_cls.return_value = mock_pc_instance
        mock_index = MagicMock()
        mock_index.name = 'hammer-index'
        mock_pc_instance.list_indexes.return_value = [mock_index]
        
        service = PineconeService()
        
        mock_client_cls.assert_called_once()
        mock_pinecone_cls.assert_called_once()
        service.pc.Index.assert_called_with('hammer-index')

    @patch('src.database.vector_store.Config')
    @patch('src.database.vector_store.Pinecone')
    @patch('src.database.vector_store.genai.Client')
    def test_embed_text_normalization(self, mock_client_cls, mock_pinecone_cls, mock_config_cls):
        mock_config_cls.PINECONE_API_KEY = 'mock_key'
        mock_config_cls.GOOGLE_API_KEY = 'mock_key'
        mock_config_cls.PINECONE_INDEX_NAME = 'hammer-index'

        mock_pc_instance = MagicMock()
        mock_pinecone_cls.return_value = mock_pc_instance
        
        # Correctly mock index name
        mock_index = MagicMock()
        mock_index.name = 'hammer-index'
        mock_pc_instance.list_indexes.return_value = [mock_index]
        
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance
        
        mock_embedding_obj = MagicMock()
        mock_embedding_obj.values = [3.0, 4.0]
        mock_result = MagicMock()
        mock_result.embeddings = [mock_embedding_obj]
        
        mock_client_instance.models.embed_content.return_value = mock_result
        
        service = PineconeService()
        embedding = service.embed_text("test")
        
        try:
            np.testing.assert_allclose(embedding, [0.6, 0.8], atol=1e-6)
            
            _, kwargs = mock_client_instance.models.embed_content.call_args
            assert kwargs['model'] == "gemini-embedding-001"
            mock_types.EmbedContentConfig.assert_called_with(output_dimensionality=1536)
        except Exception as e:
            print(f"\nASSERTION FAILED IN TEST_EMBED_TEXT: {e}")
            # check call args
            if mock_client_instance.models.embed_content.called:
                print(f"Call args: {mock_client_instance.models.embed_content.call_args}")
            if mock_types.EmbedContentConfig.called:
                 print(f"Config call args: {mock_types.EmbedContentConfig.call_args}")
            else:
                 print("Config NOT called")
            raise e

    @patch('src.database.vector_store.Config')
    @patch('src.database.vector_store.Pinecone')
    @patch('src.database.vector_store.genai.Client')
    def test_embed_documents(self, mock_client_cls, mock_pinecone_cls, mock_config_cls):
        mock_config_cls.PINECONE_API_KEY = 'mock_key'
        mock_config_cls.GOOGLE_API_KEY = 'mock_key'
        mock_config_cls.PINECONE_INDEX_NAME = 'hammer-index'
        
        mock_pc_instance = MagicMock()
        mock_pinecone_cls.return_value = mock_pc_instance
        
        # Correctly mock index name
        mock_index = MagicMock()
        mock_index.name = 'hammer-index'
        mock_pc_instance.list_indexes.return_value = [mock_index]
        
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance
        
        mock_emb1 = MagicMock()
        mock_emb1.values = [1.0, 0.0]
        mock_emb2 = MagicMock()
        mock_emb2.values = [0.0, 10.0]
        
        mock_result = MagicMock()
        mock_result.embeddings = [mock_emb1, mock_emb2]
        
        mock_client_instance.models.embed_content.return_value = mock_result
        
        service = PineconeService()
        embeddings = service.embed_documents(["a", "b"])
        
        assert len(embeddings) == 2
        np.testing.assert_allclose(embeddings[0], [1.0, 0.0], atol=1e-6)
        np.testing.assert_allclose(embeddings[1], [0.0, 1.0], atol=1e-6)

if __name__ == '__main__':
    unittest.main()
