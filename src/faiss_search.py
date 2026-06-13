import sys
import pandas as pd

from semantic_engine import SemanticEngine
from faiss_index import FaissIndex


df = pd.read_csv("data/research_corpus.csv")
documents = df["content"].fillna("").tolist()

query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "retrieval augmented generation for question answering"

engine = SemanticEngine()

document_embeddings = engine.create_embeddings(documents)

embedding_dimension = document_embeddings.shape[1]
faiss_index = FaissIndex(embedding_dimension)
faiss_index.build(document_embeddings)

query_embedding = engine.create_embeddings([query])
scores, indices = faiss_index.search(query_embedding, top_k=10)

print(f"\nLoaded {len(df)} research papers")

print("\nUser Query:")
print(query)

print("\nTop FAISS Search Results:\n")

for rank, index in enumerate(indices, start=1):
    index = int(index)
    score = float(scores[rank - 1])

    title = df.iloc[index].get("title", "Untitled Paper")
    category = df.iloc[index].get("category", "Unknown Category")
    url = df.iloc[index].get("url", "")

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"FAISS Score: {score:.4f}")

    if isinstance(url, str) and url.strip():
        print(f"URL: {url}")

    print()