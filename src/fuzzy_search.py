from rapidfuzz import process, fuzz


def get_query_suggestions(query, titles, limit=5):
    if not query.strip():
        return []

    matches = process.extract(
        query,
        titles,
        scorer=fuzz.WRatio,
        limit=limit
    )

    suggestions = []

    for title, score, _ in matches:
        suggestions.append(
            {
                "suggestion": title,
                "score": score
            }
        )

    return suggestions


def get_best_query_correction(query, titles, minimum_score=60):
    suggestions = get_query_suggestions(
        query=query,
        titles=titles,
        limit=1
    )

    if not suggestions:
        return query

    best_suggestion = suggestions[0]

    if best_suggestion["score"] >= minimum_score:
        return best_suggestion["suggestion"]

    return query