from sentence_transformers import SentenceTransformer, util


class SemanticEngine:

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def create_embeddings(self, documents):
        return self.model.encode(documents, convert_to_tensor=True)

    def create_query_embedding(self, query):
        return self.model.encode([query], convert_to_tensor=True)

    def search(self, query, documents, document_embeddings):
        query_embedding = self.model.encode(
            query,
            convert_to_tensor=True
        )

        similarity_scores = util.cos_sim(
            query_embedding,
            document_embeddings
        )[0]

        top_results = similarity_scores.argsort(descending=True)

        return top_results, similarity_scores