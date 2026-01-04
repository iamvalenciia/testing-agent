"""Verify that new format fields are being extracted correctly."""
from pinecone_service import PineconeService, IndexType
from screenshot_embedder import get_embedder

ps = PineconeService()
emb = get_embedder()
embedding = emb.embed_query("login")

# Use find_similar_steps which now returns new format fields
results = ps.find_similar_steps(embedding, top_k=1, namespace="test_execution_steps")

if results:
    r = results[0]
    print("SUCCESS - Record found!")
    print("ID:", r.get("id"))
    print("Score:", r.get("score"))
    print()
    print("--- NEW FORMAT FIELDS ---")
    print("user_prompts:", "EXISTS" if r.get("user_prompts") else "MISSING")
    print("system_logs:", "EXISTS" if r.get("system_logs") else "MISSING")
    print("urls_visited:", "EXISTS" if r.get("urls_visited") else "MISSING")
    print("actions_performed:", "EXISTS" if r.get("actions_performed") else "MISSING")
    
    # Show preview
    if r.get("user_prompts"):
        print()
        print("--- USER PROMPTS PREVIEW ---")
        print(r.get("user_prompts")[:300])
else:
    print("NO RESULTS")
