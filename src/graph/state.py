from typing import TypedDict, Annotated
import operator

class GraphState(TypedDict):
    """
    State definition for the Data Ingestion Graph.
    Attributes:
        status: Current status of the workflow
        error: Any error message encountered
        row_count: Number of rows processed
    """
    status: str
    error: str
    row_count: int
