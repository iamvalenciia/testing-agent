"""Backfill Script - Migrate existing workflows to Hybrid Search sparse index.

Run this ONCE to populate the sparse index with existing workflow data.
After running, hybrid search will work for both old and new workflows.

Usage:
    cd agent-backend
    python backfill_hybrid_index.py
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import list_workflows, load_workflow
from hybrid_search import get_hybrid_search_service
from config import HYBRID_SEARCH_ENABLED


def backfill_hybrid_index():
    """Migrate all existing workflows to the sparse index."""
    
    if not HYBRID_SEARCH_ENABLED:
        print("[ERROR] HYBRID_SEARCH_ENABLED is False. Enable it in config or .env first.")
        return
    
    print("=" * 60)
    print("HYBRID SEARCH BACKFILL - Migrating existing workflows")
    print("=" * 60)
    
    # Get hybrid search service
    hybrid_service = get_hybrid_search_service()
    
    # STEP 1: Ensure sparse index exists
    print("\n[SETUP] Ensuring sparse index exists...")
    try:
        sparse_index_name = hybrid_service.ensure_sparse_index_exists("steps-index")
        print(f"[OK] Sparse index ready: {sparse_index_name}")
    except Exception as e:
        print(f"[ERROR] Could not create sparse index: {e}")
        print("   Please check your Pinecone quota and try again.")
        return
    
    # List all existing workflows
    workflows = list_workflows()
    print(f"\nFound {len(workflows)} existing workflows to migrate.\n")
    
    if not workflows:
        print("No workflows found. Nothing to migrate.")
        return
    
    records_to_upsert = []
    
    for i, wf_summary in enumerate(workflows, 1):
        workflow_id = wf_summary.get("id")
        workflow_name = wf_summary.get("name", "Unknown")
        
        print(f"[{i}/{len(workflows)}] Processing: {workflow_name}")
        
        # Load full workflow (returns WorkflowRecord object)
        workflow = load_workflow(workflow_id)
        if not workflow:
            print(f"   [SKIP] Could not load workflow {workflow_id}")
            continue
        
        # Build searchable text (use attribute access for WorkflowRecord)
        searchable_parts = [
            workflow.name or "",
            workflow.description or "",
            " ".join(workflow.tags) if workflow.tags else "",
        ]
        
        # Add step information
        steps = workflow.steps or []
        for step in steps[:10]:  # First 10 steps
            # Steps are ActionStep objects
            if hasattr(step, 'reasoning') and step.reasoning:
                searchable_parts.append(step.reasoning[:200])
            if hasattr(step, 'url') and step.url:
                searchable_parts.append(step.url)
        
        searchable_text = " ".join(filter(None, searchable_parts))
        
        if len(searchable_text) < 10:
            print(f"   [SKIP] Insufficient searchable text")
            continue
        
        records_to_upsert.append({
            "id": f"hybrid_{workflow_id}",
            "searchable_text": searchable_text,
            "metadata": {
                "workflow_id": workflow_id,
                "workflow_name": workflow.name or "",
                "goal_description": workflow.description or "",
                "tags": workflow.tags or [],
                "step_count": len(steps),
                "backfilled": True,
            }
        })
        
        print(f"   [OK] Added to batch (text length: {len(searchable_text)})")
    
    # Upsert all records in one batch
    if records_to_upsert:
        print(f"\n{'=' * 60}")
        print(f"Upserting {len(records_to_upsert)} records to hybrid index...")
        print(f"{'=' * 60}\n")
        
        dense_count, sparse_count = hybrid_service.hybrid_upsert(
            dense_index_name="steps-index",
            records=records_to_upsert
        )
        
        print(f"\n[COMPLETE] Backfill finished!")
        print(f"   Dense index: {dense_count} vectors added")
        print(f"   Sparse index: {sparse_count} vectors added")
        print(f"\n   Hybrid search is now enabled for all {len(records_to_upsert)} workflows.")
    else:
        print("\n[WARNING] No records to upsert. Check workflow data.")


if __name__ == "__main__":
    backfill_hybrid_index()
