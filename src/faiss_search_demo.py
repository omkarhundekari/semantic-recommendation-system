import pandas as pd

from semantic_engine import SemanticEngine
from faiss_index import FaissIndex


df = pd.read_csv("data/documents.csv")
documents = df["content"].tolist()

query = "recommendation systems using graphs"

engine = SemanticEngine()

document_embeddings = engine.create_embeddings(documents)
query_embedding = engine.create_query_embedding(query)

embedding_dimension = document_embeddings.shape[1]

faiss_index = FaissIndex(embedding_dimension)
faiss_index.build(document_embeddings)

scores, indices = faiss_index.search(query_embedding, top_k=5)

print("\nUser Query:")
print(query)

print("\nFAISS Search Results:\n")

for rank, index in enumerate(indices, start=1):
    score = scores[rank - 1]

    print(f"{rank}. {df.iloc[index]['title']}")
    print(f"Category: {df.iloc[index]['category']}")
    print(f"FAISS Score: {score:.4f}")
    print()