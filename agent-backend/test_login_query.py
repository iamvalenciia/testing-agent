"""Simple test - retrieve login record from Pinecone."""
from pinecone_service import PineconeService, IndexType
from screenshot_embedder import get_embedder

ps = PineconeService()
emb = get_embedder()

query = "login"
print(f"Query: {query}")

embedding = emb.embed_query(query)
print(f"Embedding dim: {len(embedding)}")

results = ps.query_index(IndexType.STEPS, embedding, top_k=5, namespace="test_execution_steps")
print(f"Results found: {len(results)}")

target = "66e06561-a2d2-46bd-8640-8d03aaa850dc"
found = False

for m in results:
    print(f"\n--- Result ---")
    print(f"ID: {m.id}")
    print(f"Score: {m.score}")
    
    if target in m.id:
        found = True
        print("*** TARGET FOUND! ***")
    
    if m.metadata:
        print(f"Metadata keys: {list(m.metadata.keys())}")
        
        up = m.metadata.get("user_prompts", "")
        if up:
            print(f"User Prompts (first 500 chars):")
            print(up[:500])

print(f"\n\n{'='*50}")
if found:
    print("SUCCESS: Target record found!")
else:
    print("FAILED: Target record NOT found")
print(f"{'='*50}")
