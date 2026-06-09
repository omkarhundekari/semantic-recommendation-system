def reciprocal_rank_fusion(rank_lists, k=60):
    fused_scores = {}

    for rank_list in rank_lists:
        for rank, item in enumerate(rank_list, start=1):
            index = item["index"]

            if index not in fused_scores:
                fused_scores[index] = 0

            fused_scores[index] += 1 / (k + rank)

    fused_results = [
        {
            "index": index,
            "rrf_score": score
        }
        for index, score in fused_scores.items()
    ]

    fused_results = sorted(
        fused_results,
        key=lambda result: result["rrf_score"],
        reverse=True
    )

    return fused_results