from research_evidence_aggregation import aggregate_research_evidence


def test_aggregates_signals_with_traceable_paper_support():
    papers = [
        {
            "document_id": "arxiv:1111.11111",
            "title": "Retrieval for Question Answering",
            "abstract": (
                "We propose a retrieval method for open-domain question answering. "
                "Experiments on Natural Questions compare against baseline methods."
            ),
            "category": "cs.IR",
            "retrieval_rank": 1,
        },
        {
            "document_id": "arxiv:2222.22222",
            "title": "Reliable RAG Systems",
            "abstract": (
                "Retrieval-augmented generation improves question answering, but "
                "irrelevant context can reduce retrieval quality. We evaluate our "
                "approach on TriviaQA datasets."
            ),
            "category": "cs.CL",
            "retrieval_rank": 2,
        },
    ]

    result = aggregate_research_evidence(papers)

    assert result["paper_count"] == 2
    assert result["evidence_tags"]["method"] == 2
    assert result["evidence_tags"]["application"] == 2

    retrieval = result["signals"]["methods"]["retrieval"]
    assert retrieval["paper_count"] == 2
    assert retrieval["document_ids"] == [
        "arxiv:1111.11111",
        "arxiv:2222.22222",
    ]

    question_answering = result["signals"]["applications"]["question_answering"]
    assert question_answering["paper_count"] == 2

    assert result["supporting_papers"][0]["document_id"] == "arxiv:1111.11111"
    assert result["supporting_papers"][0]["retrieval_rank"] == 1


def test_returns_empty_aggregation_for_no_papers():
    result = aggregate_research_evidence([])

    assert result["paper_count"] == 0
    assert result["evidence_tags"] == {}
    assert result["supporting_papers"] == []


def test_includes_alignment_summary_when_query_is_provided():
    papers = [
        {
            "document_id": "arxiv:5555.55555",
            "title": "Retrieval-Augmented Generation for Question Answering",
            "abstract": (
                "We improve retrieval augmented generation for question answering."
            ),
            "category": "cs.IR",
            "retrieval_rank": 1,
        },
        {
            "document_id": "arxiv:6666.66666",
            "title": "Calendar Appointment Scheduling Agents",
            "abstract": "We study scheduling conversations through dialogue agents.",
            "category": "cs.CL",
            "retrieval_rank": 2,
        },
    ]

    result = aggregate_research_evidence(
        papers,
        query="retrieval augmented generation for question answering",
    )

    assert result["alignment_summary"] == {
        "direct": 1,
        "adjacent": 0,
        "weak": 1,
    }

    assert result["supporting_papers"][0]["alignment"] == "direct"
    assert result["supporting_papers"][1]["alignment"] == "weak"


def test_passes_required_anchors_into_alignment():
    papers = [
        {
            "document_id": "arxiv:7777.77777",
            "title": "Autoscaling Resource Scheduling for Distributed Systems",
            "abstract": (
                "We study autoscaling and resource scheduling for distributed "
                "workloads."
            ),
            "category": "cs.DC",
            "retrieval_rank": 1,
        }
    ]

    result = aggregate_research_evidence(
        papers,
        query="Kubernetes resource scheduling and autoscaling",
        required_anchor_terms=["kubernetes", "autoscaling"],
    )

    paper = result["supporting_papers"][0]

    assert paper["alignment"] == "adjacent"
    assert paper["matched_required_anchor_terms"] == ["autoscaling"]
    assert result["alignment_summary"] == {
        "direct": 0,
        "adjacent": 1,
        "weak": 0,
    }
