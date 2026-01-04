"""Screenshot Embedder - Generates multimodal embeddings using Gemini.

This module takes screenshots and generates vector embeddings that can be
used for visual similarity search in Pinecone. This enables the agent to
recognize previously seen screens and retrieve relevant context.

COST OPTIMIZATION: Integrates with cache_service to avoid redundant API calls.
"""
import base64
import numpy as np
from pathlib import Path
from typing import List, Optional
from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, EMBEDDING_MODEL, MRL_DIMENSION
from cache_service import get_embedding_cache


class ScreenshotEmbedder:
    """
    Generate multimodal embeddings for screenshots using Gemini.
    
    Uses the configured model (default: gemini-embedding-001) which supports:
    - Text embeddings
    - Image embeddings (multimodal)
    - Configurable output dimensions (768, 1536, 3072)
    """
    
    MODEL_NAME = EMBEDDING_MODEL
    DIMENSION = MRL_DIMENSION  # From config, recommended for efficiency (balance of quality/size)
    TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"  # For indexing screenshots
    TASK_TYPE_QUERY = "RETRIEVAL_QUERY"  # For searching
    
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
    
    def _load_image_as_base64(self, image_path: str) -> str:
        """Load an image file and convert to base64."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """
        Normalize embedding to unit length.
        
        Required for dimensions < 3072 to ensure accurate cosine similarity.
        """
        arr = np.array(embedding)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()
    
    def embed_image(self, image_path: str, include_context: Optional[str] = None) -> List[float]:
        """
        Generate embedding from a screenshot file.
        
        Args:
            image_path: Path to the screenshot PNG file
            include_context: Optional text context to include with the image
                            (e.g., action type, URL, reasoning)
        
        Returns:
            768-dimensional embedding vector (normalized)
        """
        # Load image as base64
        image_b64 = self._load_image_as_base64(image_path)
        
        # Create content parts
        parts = []
        
        # Add image
        parts.append(types.Part.from_bytes(
            data=base64.b64decode(image_b64),
            mime_type="image/png"
        ))
        
        # Add context if provided
        if include_context:
            parts.append(types.Part(text=include_context))
        
        # Generate embedding
        result = self.client.models.embed_content(
            model=self.MODEL_NAME,
            contents=types.Content(parts=parts),
            config=types.EmbedContentConfig(
                task_type=self.TASK_TYPE_DOCUMENT,
                output_dimensionality=self.DIMENSION
            )
        )
        
        embedding = result.embeddings[0].values
        
        # Normalize for cosine similarity accuracy
        return self._normalize_embedding(embedding)
    

    
    def embed_query(self, query_text: str) -> List[float]:
        """
        Generate query embedding for text searches against images.
        
        COST OPTIMIZATION: Uses cache to avoid redundant API calls.
        
        Use this when you want to search for screenshots using natural language.
        Example: "login page with error message"
        
        Args:
            query_text: Natural language description of what to find
        
        Returns:
            768-dimensional embedding vector (normalized)
        """
        # Check cache first
        cache = get_embedding_cache()
        cached = cache.get(query_text, context="query")
        if cached:
            print(f"[CACHE] HIT for query: '{query_text[:30]}...'")
            return cached
        
        # Cache miss - call API
        result = self.client.models.embed_content(
            model=self.MODEL_NAME,
            contents=query_text,
            config=types.EmbedContentConfig(
                task_type=self.TASK_TYPE_QUERY,
                output_dimensionality=self.DIMENSION
            )
        )
        
        embedding = result.embeddings[0].values
        normalized = self._normalize_embedding(embedding)
        
        # Store in cache
        cache.set(query_text, normalized, context="query")
        print(f"[CACHE] STORED query: '{query_text[:30]}...'")
        
        return normalized
    



# Singleton instance
_embedder = None


def get_embedder() -> ScreenshotEmbedder:
    """Get the singleton ScreenshotEmbedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = ScreenshotEmbedder()
    return _embedder
