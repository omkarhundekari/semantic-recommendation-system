import pandas as pd

from persistent_cache import PersistentCache
from bm25_retriever import BM25Retriever
from rrf_fusion import reciprocal_rank_fusion


df = pd.read_csv("data/large_documents.csv")

cache = PersistentCache()

documents = df["content"].tolist()
bm25 = BM25Retriever(documents)

query = "graph neural networks recommendation systems"

faiss_scores, faiss_indices = cache.search(
    query=query,
    top_k=10
)

faiss_ranked = [
    {
        "index": int(index),
        "score": float(score)
    }
    for score, index in zip(faiss_scores, faiss_indices)
]

bm25_ranked = bm25.search(
    query=query,
    top_k=10
)

fused_results = reciprocal_rank_fusion(
    rank_lists=[faiss_ranked, bm25_ranked],
    k=60
)

print("\nRRF Fused Results:\n")

for rank, result in enumerate(fused_results[:5], start=1):
    index = result["index"]

    print(f"{rank}. {df.iloc[index]['title']}")
    print(f"Category: {df.iloc[index]['category']}")
    print(f"RRF Score: {result['rrf_score']:.4f}")
    print()