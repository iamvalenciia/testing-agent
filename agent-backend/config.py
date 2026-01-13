"""Configuration settings for the Agent Backend."""
import os
from dotenv import load_dotenv

load_dotenv()

# Google AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
MRL_DIMENSION = int(os.getenv("MRL_DIMENSION", "768"))  # Matryoshka Representation Learning dimension

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

# Test Credentials
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")
TEST_WEBSITE = os.getenv("TEST_WEBSITE", "https://test.projectgraphite.com")

# Jira Cloud API
JIRA_API = os.getenv("JIRA_API", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN", "projectgraphite.atlassian.net")

# Google OAuth (Enterprise)
# Hardcoded per user request to ensure matching with frontend
GOOGLE_CLIENT_ID = "1064806089838-m2o98dq97hha911j7ugl28p2gf367gnc.apps.googleusercontent.com"
ALLOWED_EMAIL_DOMAIN = "graphiteconnect.com"
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production-please")
SESSION_EXPIRY_DAYS = 30
