from collections import defaultdict
from typing import Any, Dict, List, Mapping

from research_evidence_alignment import classify_evidence_alignment
from research_evidence_extraction import (
    SIGNAL_ORDER,
    extract_research_evidence,
)


def build_empty_signal_groups() -> Dict[str, Dict[str, Dict[str, Any]]]:
    return {group: {} for group in SIGNAL_ORDER}


def add_signal_support(
    aggregated_signals: Dict[str, Dict[str, Dict[str, Any]]],
    group: str,
    signal: str,
    paper_evidence: Mapping[str, Any],
    paper: Mapping[str, Any],
) -> None:
    group_signals = aggregated_signals[group]

    if signal not in group_signals:
        group_signals[signal] = {
            "paper_count": 0,
            "document_ids": [],
            "supporting_papers": [],
        }

    entry = group_signals[signal]
    document_id = paper_evidence["document_id"]

    if document_id in entry["document_ids"]:
        return

    entry["paper_count"] += 1
    entry["document_ids"].append(document_id)
    entry["supporting_papers"].append(
        {
            "document_id": document_id,
            "title": paper_evidence["title"],
            "retrieval_rank": paper.get("retrieval_rank"),
            "matched_phrases": paper_evidence["matched_phrases"].get(
                signal,
                [],
            ),
            "evidence_snippets": paper_evidence["signal_snippets"].get(
                signal,
                [],
            )[:2],
        }
    )


def aggregate_research_evidence(
    papers: List[Mapping[str, Any]],
    query: str = "",
    required_anchor_terms: List[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate deterministic paper-level evidence while retaining traceability
    to supporting document IDs, retrieval ranks, matched phrases, and snippets.
    """
    if not papers:
        result = {
            "paper_count": 0,
            "evidence_tags": {},
            "signals": build_empty_signal_groups(),
            "supporting_papers": [],
        }

        if str(query or "").strip():
            result["alignment_summary"] = {
                "direct": 0,
                "adjacent": 0,
                "weak": 0,
            }

        return result

    aggregated_signals = build_empty_signal_groups()
    tag_counts = defaultdict(int)
    supporting_papers = []
    normalized_query = str(query or "").strip()
    alignment_summary = {
        "direct": 0,
        "adjacent": 0,
        "weak": 0,
    }

    for paper in papers:
        paper_evidence = extract_research_evidence(paper)

        paper_summary = {
            "document_id": paper_evidence["document_id"],
            "title": paper_evidence["title"],
            "category": paper_evidence["category"],
            "retrieval_rank": paper.get("retrieval_rank"),
            "evidence_tags": paper_evidence["evidence_tags"],
            "evidence_snippets": paper_evidence["evidence_snippets"],
        }

        if normalized_query:
            alignment = classify_evidence_alignment(
                query=normalized_query,
                paper=paper,
                required_anchor_terms=required_anchor_terms,
            )
            paper_summary.update(alignment)
            alignment_summary[alignment["alignment"]] += 1

        supporting_papers.append(paper_summary)

        for tag in paper_evidence["evidence_tags"]:
            tag_counts[tag] += 1

        for group, signals in paper_evidence["signals"].items():
            for signal in signals:
                add_signal_support(
                    aggregated_signals=aggregated_signals,
                    group=group,
                    signal=signal,
                    paper_evidence=paper_evidence,
                    paper=paper,
                )

    supporting_papers.sort(
        key=lambda item: (
            item["retrieval_rank"] is None,
            item["retrieval_rank"],
            item["document_id"],
        )
    )

    result = {
        "paper_count": len(papers),
        "evidence_tags": dict(sorted(tag_counts.items())),
        "signals": aggregated_signals,
        "supporting_papers": supporting_papers,
    }

    if normalized_query:
        result["alignment_summary"] = alignment_summary

    return result
