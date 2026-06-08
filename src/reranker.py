from sentence_transformers import CrossEncoder


class CrossEncoderReranker:

    def __init__(self):
        self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(self, query, documents):
        pairs = []

        for document in documents:
            pairs.append(
                [
                    query,
                    document["content"]
                ]
            )

        scores = self.model.predict(pairs)

        reranked_results = []

        for document, score in zip(documents, scores):
            document["rerank_score"] = float(score)
            reranked_results.append(document)

        reranked_results = sorted(
            reranked_results,
            key=lambda result: result["rerank_score"],
            reverse=True
        )

        return reranked_results