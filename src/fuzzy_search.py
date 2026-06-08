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