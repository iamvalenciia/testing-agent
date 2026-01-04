"""
Script to index the Hammer Download workflow into Pinecone's steps-index.

Run this ONCE to teach the agent about the direct hammer download capability.
After running, the agent will know to use the HammerDownloader when the user
asks to download a hammer file.

Usage:
    python index_hammer_workflow.py
"""
import os
import sys
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pinecone_service import PineconeService, IndexType


def index_hammer_download_workflow():
    """
    Index the hammer download workflow into steps-index.
    
    This teaches the agent that when users request hammer downloads,
    it should use the direct API method instead of browser automation.
    """
    print("\n" + "=" * 60)
    print("[INDEX] INDEXING HAMMER DOWNLOAD WORKFLOW")
    print("=" * 60)
    
    pinecone_service = PineconeService()
    
    # Define the workflow with multiple trigger variations
    workflow_data = {
        "id": "workflow_hammer_download_direct",
        "name": "Download Hammer File (Direct API)",
        "description": "Download and index a hammer file from a client using direct API calls. Bypasses browser automation for reliable file downloads.",
        "category": "hammer",
        "tags": ["hammer", "download", "api", "index", "xlsm"],
        "step_count": 1,  # It's a single API call now
        "execution_type": "direct_api",  # Tells agent this doesn't need browser
        "execution_summary": """
This workflow downloads a hammer file directly via the Graphite API.

TRIGGER PHRASES (English):
- "download hammer from [company]"
- "get hammer file from [company]"
- "download hammer for [company]"
- "fetch [company] hammer"

TRIGGER PHRASES (Spanish):
- "descargar hammer de [company]"
- "descarga el hammer de [company]"
- "bajar hammer de [company]"
- "obtener hammer de [company]"

EXECUTION:
1. Extract company name from user request
2. Match company name to ID using fuzzy matching
3. Call Graphite History API: GET /api/admin/tools/questions/history?filter={company_id}
4. Extract _id from first (most recent) history entry
5. Download file: GET /api/admin/tools/questions/history_download/{_id}
6. Index to Pinecone hammer-index using HammerIndexer

AVAILABLE COMPANIES:
- Western Digital Technologies, Inc. (US66254) - aliases: western, western digital, wd
- Adobe-TEST (US1229) - aliases: adobe
- Vonage TEST (US5078) - aliases: vonage
- Air Liquide (FR65911) - aliases: air liquide

NO BROWSER NEEDED - This uses direct HTTP calls.
""",
        "steps": [
            {
                "action_type": "api_call",
                "args": {
                    "method": "HammerDownloader.download_and_index()",
                    "input": "company_name",
                    "output": "indexed_records_count"
                },
                "description": "Download hammer via API and index to Pinecone"
            }
        ]
    }
    
    # Generate embedding for searchability
    text_to_embed = f"""
    download hammer file from company client
    get hammer xlsm configuration
    descargar hammer de cliente
    fetch hammer file western digital adobe vonage
    download and index hammer configuration
    """
    
    from screenshot_embedder import get_embedder
    embedder = get_embedder()
    embedding = embedder.embed_query(text_to_embed)
    
    # Upsert to steps-index
    pinecone_service.upsert_step(
        action_type="hammer_download",
        goal_description="Download Hammer File from Company",
        step_details=workflow_data,
        embedding=embedding,
        efficiency_score=1.0,  # Direct API is most efficient
    )
    
    print("[OK] Workflow indexed: 'Download Hammer File (Direct API)'")
    
    # Also index some common variations as separate entries for better matching
    variations = [
        {
            "id": "workflow_hammer_download_es",
            "goal": "Descargar archivo hammer de cliente",
            "text": "descargar hammer archivo xlsm de cliente company bajar obtener"
        },
        {
            "id": "workflow_hammer_western",
            "goal": "Download Western Digital Hammer",
            "text": "download hammer from western digital wd US66254"
        },
        {
            "id": "workflow_hammer_test_config",
            "goal": "Download hammer to test new configuration",
            "text": "download hammer to test new configuration verify ticket changes testing"
        },
    ]
    
    for var in variations:
        embedding = embedder.embed_query(var["text"])
        
        pinecone_service.upsert_step(
            action_type="hammer_download",
            goal_description=var["goal"],
            step_details={
                "id": var["id"],
                "name": var["goal"],
                "description": var["goal"],
                "execution_type": "direct_api",
                "parent_workflow": "workflow_hammer_download_direct",
                "execution_summary": workflow_data["execution_summary"],
            },
            embedding=embedding,
            efficiency_score=1.0,
        )
        print(f"[OK] Variation indexed: '{var['goal']}'")
    
    print("\n[COMPLETE] Hammer download workflow indexed to Pinecone!")
    print("The agent will now use direct API for hammer downloads.")


if __name__ == "__main__":
    index_hammer_download_workflow()
