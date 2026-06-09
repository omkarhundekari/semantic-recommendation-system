import pandas as pd

from bm25_retriever import BM25Retriever


df = pd.read_csv("data/large_documents.csv")

documents = df["content"].tolist()

bm25 = BM25Retriever(documents)

query = "graph neural networks recommendation systems"

results = bm25.search(
    query=query,
    top_k=5
)

print("\nBM25 Search Results:\n")

for rank, result in enumerate(results, start=1):
    index = result["index"]

    print(f"{rank}. {df.iloc[index]['title']}")
    print(f"Category: {df.iloc[index]['category']}")
    print(f"BM25 Score: {result['score']:.4f}")
    print()