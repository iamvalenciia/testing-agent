import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph.workflow import build_graph

def main():
    print("Graphi Connect Testing Framework - Initializing...")
    
    app = build_graph()
    
    initial_state = {"status": "Starting", "error": None, "row_count": 0}
    
    print("Running Data Ingestion Workflow...")
    # Invoke the graph
    result = app.invoke(initial_state)
    
    print("\nWorkflow Finished.")
    print(f"Final Status: {result['status']}")
    print(f"Rows Processed: {result['row_count']}")
    
    if result['error']:
        print(f"Error Encountered: {result['error']}")

if __name__ == "__main__":
    main()
