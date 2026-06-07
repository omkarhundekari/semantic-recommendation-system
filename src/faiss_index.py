import faiss
import numpy as np


class FaissIndex:

    def __init__(self, embedding_dimension):
        self.index = faiss.IndexFlatIP(embedding_dimension)

    def build(self, embeddings):
        embeddings = embeddings.cpu().numpy()
        embeddings = embeddings.astype("float32")

        faiss.normalize_L2(embeddings)

        self.index.add(embeddings)

    def search(self, query_embedding, top_k=5):
        query_embedding = query_embedding.cpu().numpy()
        query_embedding = query_embedding.astype("float32")

        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, top_k)

        return scores[0], indices[0]