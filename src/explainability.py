def normalize_word(word):
    """
    Normalize words for simple keyword overlap.
    Handles punctuation and small plural differences.
    """
    word = word.lower().strip(".,()[]{}:;-")

    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("s") and len(word) > 4:
        word = word[:-1]

    return word


def extract_keywords(text):
    """
    Extract simple meaningful keywords from a title or short text.
    This keeps the explanation lightweight and dependency-free.
    """
    stopwords = {
        "a", "an", "the", "for", "of", "in", "on", "and", "or", "to", "with",
        "using", "based", "towards", "toward", "from", "by", "via", "into",
        "are", "is", "as", "at", "over", "under"
    }

    words = text.replace(":", " ").replace("-", " ").replace("/", " ").split()

    keywords = set()

    for word in words:
        normalized_word = normalize_word(word)

        if len(normalized_word) > 3 and normalized_word not in stopwords:
            keywords.add(normalized_word)

    return keywords


def explain_recommendation(
    selected_category,
    recommended_category,
    similarity_score,
    selected_title=None,
    recommended_title=None
):
    reasons = []

    if selected_category == recommended_category:
        reasons.append(f"it belongs to the same research category ({selected_category})")
    else:
        reasons.append(
            f"it is semantically related across categories "
            f"({selected_category} → {recommended_category})"
        )

    if similarity_score >= 0.75:
        reasons.append("it has very high semantic similarity")
    elif similarity_score >= 0.60:
        reasons.append("it has strong semantic similarity")
    elif similarity_score >= 0.40:
        reasons.append("it has moderate semantic similarity")
    else:
        reasons.append("it has weaker but still relevant semantic similarity")

    if selected_title and recommended_title:
        selected_keywords = extract_keywords(selected_title)
        recommended_keywords = extract_keywords(recommended_title)

        shared_keywords = selected_keywords.intersection(recommended_keywords)

        if shared_keywords:
            top_keywords = sorted(list(shared_keywords))[:5]
            keyword_text = ", ".join(top_keywords)
            reasons.append(f"both titles share key research terms: {keyword_text}")

    explanation = "Recommended because " + ", ".join(reasons) + "."

    return explanation