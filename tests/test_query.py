"""Test query functionality."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.vector_store import PineconeService

def main():
    ps = PineconeService()
    
    # Test different queries to verify multi-sheet ingestion
    queries = [
        "group definitions",
        "master question list",
        "overrides",
        "triggers workflow",
        "risk connections"
    ]
    
    for query in queries:
        print(f"\n--- Query: '{query}' ---")
        results = ps.query(query, top_k=3)
        for r in results:
            sheet = r.get('metadata', {}).get('sheet_name', 'unknown')
            print(f"  Score: {r['score']:.4f} | Sheet: {sheet} | ID: {r['id']}")

if __name__ == "__main__":
    main()
