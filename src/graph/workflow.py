from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.agents.librarian import LibrarianAgent

# Initialize Agent
librarian = LibrarianAgent()

def node_ingest(state: GraphState):
    """
    Node to run the data ingestion process.
    Uses clean_ingest to ensure data consistency by deleting old vectors first.
    """
    try:
        # Use clean_ingest to delete old vectors before inserting new ones
        count = librarian.clean_ingest()
        return {"status": "Complete", "row_count": count, "error": None}
    except Exception as e:
        return {"status": "Failed", "error": str(e), "row_count": 0}

def build_graph():
    """Construct the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    
    # Define Nodes
    workflow.add_node("librarian_ingest", node_ingest)
    
    # Define Entry Point
    workflow.set_entry_point("librarian_ingest")
    
    # Define Edges
    # For now, simple linear flow: Ingest -> End
    workflow.add_edge("librarian_ingest", END)
    
    return workflow.compile()
