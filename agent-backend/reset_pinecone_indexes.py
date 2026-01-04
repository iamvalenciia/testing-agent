"""
Script to reset Pinecone indexes with correct dimensions (MRL_DIMENSION from config).
This will DELETE all existing data in these indexes.
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from config import MRL_DIMENSION

def reset_indexes():
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("[ERROR] PINECONE_API_KEY not found in environment")
        return False
    
    pc = Pinecone(api_key=api_key)
    
    # Indexes to reset
    indexes_to_reset = ["hammer-index", "steps-index", "steps-sparse"]
    
    existing = pc.list_indexes().names()
    print(f"Existing indexes: {existing}")
    
    for index_name in indexes_to_reset:
        if index_name in existing:
            print(f"\n[DELETE] Deleting {index_name}...")
            try:
                pc.delete_index(index_name)
                print(f"[OK] Deleted {index_name}")
            except Exception as e:
                print(f"[ERROR] Failed to delete {index_name}: {e}")
        else:
            print(f"[SKIP] {index_name} does not exist")
    
    print("\n" + "="*60)
    print("DONE. Restart your backend (python main.py) to recreate")
    print(f"indexes with correct {MRL_DIMENSION} dimensions for Gemini embeddings.")
    print("="*60)
    return True

if __name__ == "__main__":
    confirm = input("This will DELETE hammer-index and steps-index. Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        reset_indexes()
    else:
        print("Cancelled.")
