import os
import sys
import faiss
import pandas as pd

from semantic_engine import SemanticEngine


index_path = "indexes/research_papers.index"

if not os.path.exists(index_path):
    print("FAISS index not found. Run: python src/build_faiss_index.py")
    sys.exit(1)

df = pd.read_csv("data/research_corpus.csv")

query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "retrieval augmented generation for question answering"

engine = SemanticEngine()
index = faiss.read_index(index_path)

query_embedding = engine.create_embeddings([query])
query_embedding = query_embedding.cpu().numpy().astype("float32")
faiss.normalize_L2(query_embedding)

scores, indices = index.search(query_embedding, 10)

print(f"\nLoaded {len(df)} research papers")
print(f"Loaded FAISS index from {index_path}")

print("\nUser Query:")
print(query)

print("\nTop FAISS Search Results:\n")

for rank, index_value in enumerate(indices[0], start=1):
    index_value = int(index_value)
    score = float(scores[0][rank - 1])

    title = df.iloc[index_value].get("title", "Untitled Paper")
    category = df.iloc[index_value].get("category", "Unknown Category")
    url = df.iloc[index_value].get("url", "")

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"FAISS Score: {score:.4f}")

    if isinstance(url, str) and url.strip():
        print(f"URL: {url}")

    print()