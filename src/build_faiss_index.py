import os
import faiss
import pandas as pd

from semantic_engine import SemanticEngine
from faiss_index import FaissIndex


df = pd.read_csv("data/research_corpus.csv")
documents = df["content"].fillna("").tolist()

engine = SemanticEngine()
document_embeddings = engine.create_embeddings(documents)

embedding_dimension = document_embeddings.shape[1]
faiss_index = FaissIndex(embedding_dimension)
faiss_index.build(document_embeddings)

os.makedirs("indexes", exist_ok=True)
faiss.write_index(faiss_index.index, "indexes/research_papers.index")

print(f"Saved FAISS index for {len(df)} research papers")