from persistent_cache import PersistentCache
from reranker import CrossEncoderReranker


cache = PersistentCache()
reranker = CrossEncoderReranker()

query = "graph neural networks for recommendation systems"

scores, indices = cache.search(
    query=query,
    top_k=20
)

candidate_documents = []

for score, index in zip(scores, indices):
    index = int(index)

    candidate_documents.append(
        {
            "title": cache.df.iloc[index]["title"],
            "category": cache.df.iloc[index]["category"],
            "content": cache.df.iloc[index]["content"],
            "semantic_score": float(score)
        }
    )

reranked_results = reranker.rerank(
    query=query,
    documents=candidate_documents
)

print("\nCrossEncoder Reranked Results:\n")

for rank, result in enumerate(reranked_results[:5], start=1):
    print(f"{rank}. {result['title']}")
    print(f"Category: {result['category']}")
    print(f"Semantic Score: {result['semantic_score']:.4f}")
    print(f"Rerank Score: {result['rerank_score']:.4f}")
    print()