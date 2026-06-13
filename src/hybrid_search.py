import re


def tokenize(text):
    return set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9]+\b", text.lower()))


def calculate_keyword_score(query, document):
    query_words = tokenize(query)
    document_words = tokenize(document)

    if not query_words:
        return 0

    matching_words = query_words.intersection(document_words)

    return len(matching_words) / len(query_words)


def calculate_hybrid_score(semantic_score, keyword_score, semantic_weight=0.7, keyword_weight=0.3):
    return (semantic_weight * semantic_score) + (keyword_weight * keyword_score)