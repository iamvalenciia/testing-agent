
import sys
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Add directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pinecone_service import PineconeService, IndexType
from config import MRL_DIMENSION

def verify_retrieval():
    print("Initializing Pinecone Service...")
    ps = PineconeService()
    
    target_workflow_id = "workflow_hammer_download_hammer_to_test_config"
    print(f"\nAttempting to fetch step with workflow_id: {target_workflow_id}")
    
    step = ps.find_step_by_workflow_id(target_workflow_id)
    
    if step:
        print("\n[SUCCESS] Found step record!")
        print(f"ID: {step.get('id')}")
        print(f"Workflow Name: {step.get('workflow_name')}")
        
        text = step.get('text') or ""
        print(f"Text content length: {len(text)}")
        
        if "COMPANIES =" in text:
            print("\n[SUCCESS] 'COMPANIES =' block found in text.")
            
            # Verify parsing
            from hammer_downloader import parse_companies_from_text
            companies = parse_companies_from_text(text)
            print(f"Parsed {len(companies)} companies:")
            for c in companies:
                print(f" - {c.get('company_name')}")
        else:
            print("\n[FAIL] 'COMPANIES =' block NOT found in text.")
            print("Text content preview:")
            print(text[:200])
            
    else:
        print("\n[FAIL] Could not find step by workflow_id.")
        print("Debugging info:")
        try:
            # Try listing some steps to see what's in there
            matches = ps.find_similar_steps([0.0]*MRL_DIMENSION, top_k=5)
            print("\nTop 5 generic matches in index:")
            for m in matches:
                print(f" - ID: {m['id']}")
                print(f"   Workflow ID: {m.get('workflow_id', 'N/A')}")
                print(f"   Metadata keys: {m.keys()}")
        except Exception as e:
            print(f"Error listing steps: {e}")

if __name__ == "__main__":
    verify_retrieval()
