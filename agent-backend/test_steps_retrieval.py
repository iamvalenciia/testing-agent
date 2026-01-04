"""Test for retrieving records from Pinecone steps-index.

This test verifies that we can retrieve records from the test_execution_steps
namespace by querying with a simple word like "login".

Target record:
- ID: 66e06561-a2d2-46bd-8640-8d03aaa850dc_20260103022151
- Namespace: test_execution_steps
"""
from pinecone_service import PineconeService, IndexType
from screenshot_embedder import get_embedder


def test_retrieve_login_record():
    """
    Test retrieving the login workflow record by querying with 'login'.
    
    Expected to find record with ID containing: 66e06561-a2d2-46bd-8640-8d03aaa850dc
    """
    # Initialize services
    pinecone_service = PineconeService()
    embedder = get_embedder()
    
    # Generate embedding for "login"
    query_text = "login"
    query_embedding = embedder.embed_query(query_text)
    
    print(f"\n{'='*60}")
    print(f"[TEST] Query: '{query_text}'")
    print(f"[TEST] Embedding dimension: {len(query_embedding)}")
    print(f"[TEST] Namespace: test_execution_steps")
    print(f"{'='*60}")
    
    # Query the steps-index with test_execution_steps namespace
    results = pinecone_service.query_index(
        index_type=IndexType.STEPS,
        query_vector=query_embedding,
        top_k=5,
        namespace="test_execution_steps"
    )
    
    print(f"\n[TEST] Found {len(results)} results:")
    
    # Display results
    target_id_prefix = "66e06561-a2d2-46bd-8640-8d03aaa850dc"
    found_target = False
    
    for i, match in enumerate(results):
        print(f"\n  [{i+1}] ID: {match.id}")
        print(f"      Score: {match.score:.4f}")
        
        # Check if this is our target record
        if target_id_prefix in match.id:
            found_target = True
            print(f"      ✅ THIS IS THE TARGET RECORD!")
        
        # Print metadata
        if hasattr(match, 'metadata') and match.metadata:
            print(f"      Metadata keys: {list(match.metadata.keys())}")
            
            # Print user_prompts if available (first 300 chars)
            if 'user_prompts' in match.metadata:
                prompts = match.metadata['user_prompts']
                print(f"\n      --- User Prompts ---")
                print(f"      {prompts[:300]}...")
            
            # Print URLs visited if available (first 300 chars)
            if 'urls_visited' in match.metadata:
                urls = match.metadata['urls_visited']
                print(f"\n      --- URLs Visited ---")
                print(f"      {urls[:300]}...")
            
            # Print actions performed if available
            if 'actions_performed' in match.metadata:
                actions = match.metadata['actions_performed']
                print(f"\n      --- Actions Performed ---")
                print(f"      {actions[:300]}...")
    
    # Summary
    print(f"\n{'='*60}")
    if found_target:
        print(f"✅ SUCCESS: Found target record with ID prefix: {target_id_prefix}")
    else:
        print(f"❌ FAILED: Did not find record with ID prefix: {target_id_prefix}")
        print(f"   Available IDs: {[m.id for m in results]}")
    print(f"{'='*60}")
    
    return found_target


def test_steps_index_stats():
    """Test getting stats from steps-index to verify namespace exists."""
    pinecone_service = PineconeService()
    index = pinecone_service.get_index(IndexType.STEPS)
    stats = index.describe_index_stats()
    
    print(f"\n{'='*60}")
    print(f"[TEST] Steps Index Stats:")
    print(f"  Total vectors: {stats.total_vector_count}")
    print(f"  Dimension: {stats.dimension}")
    
    # Check namespaces
    if stats.namespaces:
        print(f"  Namespaces found: {len(stats.namespaces)}")
        for ns_name, ns_stats in stats.namespaces.items():
            print(f"    - {ns_name}: {ns_stats.vector_count} vectors")
    else:
        print(f"  ⚠️ No namespaces found!")
    print(f"{'='*60}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print(" PINECONE STEPS-INDEX RETRIEVAL TEST")
    print("="*60)
    
    # First show index stats
    test_steps_index_stats()
    
    # Then test retrieval
    success = test_retrieve_login_record()
    
    exit(0 if success else 1)
