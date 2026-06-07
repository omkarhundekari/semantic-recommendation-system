def explain_recommendation(selected_category, recommended_category, similarity_score):
    reasons = []

    if selected_category == recommended_category:
        reasons.append(
            "both documents belong to the same category"
        )
    else:
        reasons.append(
            "the documents are semantically related even though they belong to different categories"
        )

    if similarity_score >= 0.50:
        reasons.append(
            "the semantic similarity score is strong"
        )
    elif similarity_score >= 0.30:
        reasons.append(
            "the semantic similarity score is moderate"
        )
    else:
        reasons.append(
            "the semantic similarity score is weaker but still relevant"
        )

    explanation = "Recommended because " + " and ".join(reasons) + "."

    return explanation