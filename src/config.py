import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENV = os.getenv("PINECONE_ENV", "gcp-starter") 
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "hammer-index")
    HAMMER_FILE_PATH = os.getenv("HAMMER_FILE_PATH", "data/hammer.xlsm")

    @classmethod
    def validate(cls):
        """Ensure critical environment variables are set."""
        required = ["GOOGLE_API_KEY", "PINECONE_API_KEY"]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
