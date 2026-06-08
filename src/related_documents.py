from semantic_engine import SemanticEngine
from faiss_index import FaissIndex


class RelatedDocuments:

    def __init__(self, dataframe):
        self.df = dataframe
        self.documents = dataframe["content"].tolist()

        self.engine = SemanticEngine()
        self.document_embeddings = self.engine.create_embeddings(self.documents)

        embedding_dimension = self.document_embeddings.shape[1]

        self.faiss_index = FaissIndex(embedding_dimension)
        self.faiss_index.build(self.document_embeddings)

    def get_related_documents(self, title, top_k=5):
        matching_rows = self.df[
            self.df["title"].str.lower() == title.lower()
        ]

        if matching_rows.empty:
            return []

        selected_index = matching_rows.index[0]
        selected_content = self.df.iloc[selected_index]["content"]

        query_embedding = self.engine.create_query_embedding(selected_content)

        scores, indices = self.faiss_index.search(
            query_embedding,
            top_k + 1
        )

        related_results = []

        for score, index in zip(scores, indices):
            index = int(index)

            if index == selected_index:
                continue

            related_results.append(
                {
                    "title": self.df.iloc[index]["title"],
                    "category": self.df.iloc[index]["category"],
                    "score": float(score)
                }
            )

        return related_results[:top_k]