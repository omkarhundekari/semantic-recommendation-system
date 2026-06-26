from research_query_anchors import extract_required_anchor_terms


def test_extracts_rag_and_question_answering_anchors():
    anchors = extract_required_anchor_terms(
        "build a retrieval augmented generation project for question answering"
    )

    assert anchors == [
        "retrieval augmented generation",
        "question answering",
    ]


def test_extracts_kubernetes_and_autoscaling_anchors():
    anchors = extract_required_anchor_terms(
        "build a kubernetes resource scheduling and autoscaling project"
    )

    assert anchors == [
        "kubernetes",
        "autoscaling",
    ]


def test_returns_no_anchors_for_general_project_request():
    anchors = extract_required_anchor_terms(
        "build a portfolio project for software engineering roles"
    )

    assert anchors == []
