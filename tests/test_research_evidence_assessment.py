from research_evidence_assessment import build_evidence_assessment


def test_builds_traceable_evidence_assessment():
    papers = [
        {
            "document_id": "arxiv:8888.88888",
            "title": "Retrieval-Augmented Generation for Question Answering",
            "abstract": (
                "We improve retrieval augmented generation for question answering "
                "with a retrieval method."
            ),
            "category": "cs.IR",
            "retrieval_rank": 1,
        },
        {
            "document_id": "arxiv:9999.99999",
            "title": "Retrieval-Augmented Generation Evaluation",
            "abstract": (
                "We evaluate retrieval augmented generation systems for "
                "question answering."
            ),
            "category": "cs.IR",
            "retrieval_rank": 2,
        },
        {
            "document_id": "arxiv:1010.10101",
            "title": "Practical Retrieval-Augmented Generation",
            "abstract": (
                "We study retrieval augmented generation applications for "
                "question answering."
            ),
            "category": "cs.IR",
            "retrieval_rank": 3,
        },
    ]

    result = build_evidence_assessment(
        papers,
        query="retrieval augmented generation for question answering",
    )

    assert result["query"] == "retrieval augmented generation for question answering"
    assert result["confidence"]["level"] == "strong"
    assert result["evidence"]["alignment_summary"]["direct"] == 3
    assert result["evidence"]["supporting_papers"][0]["document_id"] == "arxiv:8888.88888"
