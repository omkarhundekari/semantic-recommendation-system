def calculate_keyword_score(query, document):
    query_words = set(query.lower().split())
    document_words = set(document.lower().split())

    if not query_words:
        return 0

    matching_words = query_words.intersection(document_words)

    keyword_score = len(matching_words) / len(query_words)

    return keyword_score


def calculate_hybrid_score(semantic_score, keyword_score, semantic_weight=0.7, keyword_weight=0.3):
    hybrid_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)

    return hybrid_score