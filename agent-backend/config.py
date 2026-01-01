"""Configuration settings for the Agent Backend."""
import os
from dotenv import load_dotenv

load_dotenv()

# Google AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Pinecone
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "agent-workflows")

# Browser
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# Agent
MAX_AGENT_TURNS = 20

# Hybrid Search (Semantic + Keyword)
HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
HYBRID_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.5"))  # 0=all keyword, 1=all semantic
HYBRID_TOP_K_MULTIPLIER = int(os.getenv("HYBRID_TOP_K_MULTIPLIER", "3"))  # Over-fetch for fusion
