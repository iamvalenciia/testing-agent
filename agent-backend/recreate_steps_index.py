"""Script to recreate steps-index with correct dimension (768).

This script:
1. Deletes the existing steps-index (dimension 1024)
2. Creates a new steps-index with dimension 768 and metric=dotproduct (for hybrid search)

Run this ONCE to fix the dimension mismatch error.
"""
import os
import sys
from time import sleep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, MRL_DIMENSION

def recreate_steps_index():
    """Recreate steps-index with correct dimension."""
    
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    print("=" * 60)
    print("RECREATING STEPS-INDEX WITH CORRECT DIMENSION")
    print("=" * 60)
    print(f"\nTarget dimension: {MRL_DIMENSION}")
    print(f"Metric: dotproduct (required for hybrid search)")
    
    # Check current indexes
    existing = pc.list_indexes().names()
    print(f"\nExisting indexes: {existing}")
    
    # Delete steps-index if exists
    if "steps-index" in existing:
        print("\n[1/3] Deleting old steps-index...")
        pc.delete_index("steps-index")
        print("   ✓ Deleted steps-index")
        
        # Wait for deletion to complete
        print("   Waiting for deletion to complete...")
        sleep(5)
    else:
        print("\n[1/3] steps-index does not exist, skipping deletion")
    
    # Create new steps-index with correct dimension
    print("\n[2/3] Creating new steps-index...")
    try:
        pc.create_index(
            name="steps-index",
            dimension=MRL_DIMENSION,  # 768 for Gemini
            metric="dotproduct",  # Required for hybrid dense+sparse
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        print(f"   ✓ Created steps-index (dimension={MRL_DIMENSION}, metric=dotproduct)")
    except Exception as e:
        print(f"   ✗ Failed to create: {e}")
        return False
    
    # Wait for index to be ready
    print("\n[3/3] Waiting for index to be ready...")
    sleep(10)
    
    # Verify
    try:
        index = pc.Index("steps-index")
        stats = index.describe_index_stats()
        print(f"   ✓ Index ready! Dimension: {stats.dimension}, Vectors: {stats.total_vector_count}")
    except Exception as e:
        print(f"   ⚠ Could not verify: {e}")
    
    print("\n" + "=" * 60)
    print("DONE! steps-index recreated successfully.")
    print("=" * 60)
    print("\nYou can now restart your backend server.")
    
    return True


if __name__ == "__main__":
    recreate_steps_index()
