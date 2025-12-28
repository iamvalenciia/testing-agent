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
