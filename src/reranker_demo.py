import sys

from persistent_cache import PersistentCache
from reranker import CrossEncoderReranker


query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "graph neural networks for recommendation systems"

cache = PersistentCache()
reranker = CrossEncoderReranker()

scores, indices = cache.search(
    query=query,
    top_k=50
)

candidate_documents = []

for score, index in zip(scores, indices):
    index = int(index)

    row = cache.df.iloc[index]

    candidate_documents.append({
        "title": row.get("title", "Untitled Paper"),
        "category": row.get("category", "Unknown Category"),
        "content": row.get("content", ""),
        "url": row.get("url", ""),
        "semantic_score": float(score)
    })

reranked_results = reranker.rerank(
    query=query,
    documents=candidate_documents
)

print(f"\nLoaded {len(cache.df)} research papers")

print("\nUser Query:")
print(query)

print("\nTop Reranked Results:\n")

for rank, result in enumerate(reranked_results[:10], start=1):
    print(f"{rank}. {result['title']}")
    print(f"Category: {result['category']}")
    print(f"Semantic Score: {result['semantic_score']:.4f}")
    print(f"Rerank Score: {result['rerank_score']:.4f}")

    if isinstance(result["url"], str) and result["url"].strip():
        print(f"URL: {result['url']}")

    print()