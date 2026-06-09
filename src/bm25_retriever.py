import math
from collections import Counter


class BM25Retriever:

    def __init__(self, documents, k1=1.5, b=0.75):
        self.documents = documents
        self.tokenized_documents = [
            self._tokenize(document)
            for document in documents
        ]

        self.k1 = k1
        self.b = b

        self.document_count = len(self.tokenized_documents)
        self.document_lengths = [
            len(document)
            for document in self.tokenized_documents
        ]

        self.average_document_length = (
            sum(self.document_lengths) / self.document_count
        )

        self.document_frequencies = self._calculate_document_frequencies()

    def _tokenize(self, text):
        return text.lower().split()

    def _calculate_document_frequencies(self):
        document_frequencies = {}

        for document in self.tokenized_documents:
            unique_terms = set(document)

            for term in unique_terms:
                document_frequencies[term] = (
                    document_frequencies.get(term, 0) + 1
                )

        return document_frequencies

    def _idf(self, term):
        document_frequency = self.document_frequencies.get(term, 0)

        return math.log(
            1 + (
                (self.document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
        )

    def score(self, query, document_index):
        query_terms = self._tokenize(query)
        document = self.tokenized_documents[document_index]
        term_counts = Counter(document)

        document_length = self.document_lengths[document_index]

        score = 0

        for term in query_terms:
            if term not in term_counts:
                continue

            term_frequency = term_counts[term]
            idf = self._idf(term)

            numerator = term_frequency * (self.k1 + 1)

            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * (
                    document_length / self.average_document_length
                )
            )

            score += idf * (numerator / denominator)

        return score

    def search(self, query, top_k=5):
        scores = []

        for index in range(self.document_count):
            score = self.score(query, index)

            scores.append(
                {
                    "index": index,
                    "score": score
                }
            )

        ranked_results = sorted(
            scores,
            key=lambda result: result["score"],
            reverse=True
        )

        return ranked_results[:top_k]