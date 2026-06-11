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

    def __init__(self, csv_path="data/research_corpus.csv"):
        self.df = pd.read_csv(csv_path)
        self.documents = self.df["content"].tolist()
        self.engine = None

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

            self._load_engine()

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

    def _load_engine(self):
        if self.engine is None:
            self.engine = SemanticEngine()

    def _create_query_embedding(self, query):
        self._load_engine()

        query_embedding = self.engine.create_query_embedding(query)

        if hasattr(query_embedding, "cpu"):
            query_embedding = query_embedding.cpu().numpy()

        query_embedding = query_embedding.astype("float32")
        faiss.normalize_L2(query_embedding)

        return query_embedding

    def search(self, query, top_k=5):
        query_embedding = self._create_query_embedding(query)

        scores, indices = self.faiss_index.search(
            query_embedding,
            top_k
        )

        return scores[0], indices[0]

    def search_by_categories(self, query, selected_categories, top_k=5):
        query_embedding = self._create_query_embedding(query)

        selected_indices = self.df[
            self.df["category"].isin(selected_categories)
        ].index.tolist()

        if not selected_indices:
            return [], []

        selected_embeddings = self.document_embeddings[selected_indices]

        temp_index = faiss.IndexFlatIP(selected_embeddings.shape[1])
        temp_index.add(selected_embeddings)

        scores, local_indices = temp_index.search(
            query_embedding,
            min(top_k, len(selected_indices))
        )

        global_indices = [
            selected_indices[int(local_index)]
            for local_index in local_indices[0]
        ]

        return scores[0], global_indices