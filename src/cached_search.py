import pandas as pd

from semantic_engine import SemanticEngine
from faiss_index import FaissIndex


class CachedSearch:

    def __init__(self, csv_path="data/large_documents.csv"):

        self.df = pd.read_csv(csv_path)

        self.documents = self.df["content"].tolist()

        self.engine = SemanticEngine()

        print("Generating embeddings...")

        self.document_embeddings = self.engine.create_embeddings(
            self.documents
        )

        embedding_dimension = self.document_embeddings.shape[1]

        print("Building FAISS index...")

        self.faiss_index = FaissIndex(embedding_dimension)

        self.faiss_index.build(self.document_embeddings)

        print("Cached search ready.")

    def search(self, query, top_k=5):

        query_embedding = self.engine.create_query_embedding(query)

        scores, indices = self.faiss_index.search(
            query_embedding,
            top_k=top_k
        )

        return scores, indices