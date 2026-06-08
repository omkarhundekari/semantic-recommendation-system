import os
import pickle

import faiss
import numpy as np
import pandas as pd

from semantic_engine import SemanticEngine


EMBEDDINGS_PATH = "cache/document_embeddings.npy"
FAISS_INDEX_PATH = "cache/faiss.index"
METADATA_PATH = "cache/metadata.pkl"


class PersistentCache:

    def __init__(self, csv_path="data/large_documents.csv"):
        self.df = pd.read_csv(csv_path)
        self.documents = self.df["content"].tolist()
        self.engine = SemanticEngine()

        if (
            os.path.exists(EMBEDDINGS_PATH)
            and os.path.exists(FAISS_INDEX_PATH)
            and os.path.exists(METADATA_PATH)
        ):
            print("Loading cache from disk...")

            self.document_embeddings = np.load(EMBEDDINGS_PATH)
            self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)

            with open(METADATA_PATH, "rb") as file:
                self.metadata = pickle.load(file)

            print("Cache loaded successfully.")

        else:
            print("Generating embeddings...")

            embeddings = self.engine.create_embeddings(self.documents)

            if hasattr(embeddings, "cpu"):
                embeddings = embeddings.cpu().numpy()

            self.document_embeddings = embeddings.astype("float32")

            faiss.normalize_L2(self.document_embeddings)

            embedding_dimension = self.document_embeddings.shape[1]

            self.faiss_index = faiss.IndexFlatIP(embedding_dimension)
            self.faiss_index.add(self.document_embeddings)

            self.metadata = {
                "num_documents": len(self.documents),
                "embedding_dimension": embedding_dimension
            }

            np.save(EMBEDDINGS_PATH, self.document_embeddings)
            faiss.write_index(self.faiss_index, FAISS_INDEX_PATH)

            with open(METADATA_PATH, "wb") as file:
                pickle.dump(self.metadata, file)

            print("Cache saved successfully.")

    def search(self, query, top_k=5):
        query_embedding = self.engine.create_query_embedding(query)

        if hasattr(query_embedding, "cpu"):
            query_embedding = query_embedding.cpu().numpy()

        query_embedding = query_embedding.astype("float32")

        faiss.normalize_L2(query_embedding)

        scores, indices = self.faiss_index.search(
            query_embedding,
            top_k
        )

        return scores[0], indices[0]