from research_evidence_alignment import classify_evidence_alignment


def test_marks_direct_rag_question_answering_evidence():
    result = classify_evidence_alignment(
        query="retrieval augmented generation for question answering",
        paper={
            "title": "Retrieval-Augmented Generation for Open-Domain Question Answering",
            "abstract": (
                "We improve retrieval quality for RAG question-answering systems."
            ),
        },
    )

    assert result["alignment"] == "direct"
    assert "retrieval" in result["matched_query_terms"]
    assert "question" in result["matched_query_terms"]


def test_marks_related_but_non_kubernetes_scheduling_as_adjacent():
    result = classify_evidence_alignment(
        query="Kubernetes resource scheduling and autoscaling",
        paper={
            "title": "Resource-Constrained Project Scheduling",
            "abstract": (
                "We study optimization algorithms for resource scheduling."
            ),
        },
    )

    assert result["alignment"] == "adjacent"
    assert "scheduling" in result["matched_query_terms"]


def test_marks_unrelated_paper_as_weak():
    result = classify_evidence_alignment(
        query="Kubernetes resource scheduling and autoscaling",
        paper={
            "title": "Natural Language Dialogue for Appointment Booking",
            "abstract": "We study dialogue agents for calendar scheduling.",
        },
    )

    assert result["alignment"] == "weak"
    assert result["matched_query_terms"] == ["scheduling"]


def test_records_matching_query_phrases_for_direct_evidence():
    result = classify_evidence_alignment(
        query="retrieval augmented generation for question answering",
        paper={
            "title": "Retrieval-Augmented Generation for Open-Domain Question Answering",
            "abstract": "We evaluate a retrieval augmented generation pipeline.",
        },
    )

    assert result["alignment"] == "direct"
    assert "retrieval augmented generation" in result["matched_query_phrases"]
    assert "question answering" in result["matched_query_phrases"]


def test_keeps_general_phrase_match_adjacent_without_specific_query_anchors():
    result = classify_evidence_alignment(
        query="Kubernetes resource scheduling and autoscaling",
        paper={
            "title": "Resource Scheduling for Distributed Systems",
            "abstract": (
                "We propose resource scheduling algorithms for distributed workloads."
            ),
        },
    )

    assert result["alignment"] == "adjacent"
    assert "resource scheduling" in result["matched_query_phrases"]
    assert "kubernetes" not in result["matched_query_terms"]
    assert "autoscaling" not in result["matched_query_terms"]


def test_requires_a_specific_query_anchor_for_direct_multi_term_overlap():
    result = classify_evidence_alignment(
        query="Kubernetes resource scheduling and autoscaling",
        paper={
            "title": "Resource Scheduling in Distributed Systems",
            "abstract": (
                "We study resource scheduling algorithms for scalable workloads "
                "and distributed infrastructure."
            ),
        },
    )

    assert result["alignment"] == "adjacent"
    assert "resource" in result["matched_query_terms"]
    assert "scheduling" in result["matched_query_terms"]
    assert "kubernetes" not in result["matched_query_terms"]
    assert "autoscaling" not in result["matched_query_terms"]


def test_downgrades_direct_overlap_when_required_anchor_is_missing():
    result = classify_evidence_alignment(
        query="Kubernetes resource scheduling and autoscaling",
        required_anchor_terms=["kubernetes", "autoscaling"],
        paper={
            "title": "Resource Scheduling and Autoscaling in Distributed Systems",
            "abstract": (
                "We study resource scheduling and autoscaling for distributed "
                "workloads."
            ),
        },
    )

    assert result["alignment"] == "adjacent"
    assert result["matched_required_anchor_terms"] == ["autoscaling"]
