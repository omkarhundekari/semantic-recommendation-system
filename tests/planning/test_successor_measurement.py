from planning.candidate_models import CandidateDirection
from planning.successor_measurement import (
    build_successor_measurement_report,
    measure_successor_case,
)


CASE = {
    "id": "incident",
    "user_goal": "Build an incident investigation project.",
    "skill_level": "intermediate",
    "time_available": "2 weeks",
    "target_roles": ["Platform Engineer"],
    "preferred_stack": ["Python"],
}


class Provider:
    model = "test-model"

    def __init__(self):
        self.last_usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }


class Result:
    def __init__(
        self,
        status="ready",
        candidates=None,
        assessment=None,
    ):
        self.status = status
        self.candidates = candidates or []
        self.assessment = assessment
        self.diagnostics = {"reason_code": status}

    @property
    def ready(self):
        return self.status == "ready"


class Scorer:
    pass


def candidate(title):
    return CandidateDirection(
        title=title,
        problem_statement="Investigations are fragmented.",
        target_user="Platform engineers",
        core_workflow=["Load events.", "Correlate signals."],
        mvp_scope=[
            "Load records.",
            "Correlate events.",
            "Show timeline.",
        ],
        success_metrics=["Reduce investigation time."],
        evidence_relationship="Uses retained evidence.",
        source_ids=["paper-1"],
        assumptions=[],
        suggested_stack=["Python"],
    )


def test_case_passes_inferred_focus_without_general_fallback(
    monkeypatch,
):
    captured = {}

    def retrieve(**kwargs):
        return {
            "inference": {"inferred_focus": None},
            "merged_results": [{"id": "paper-1"}],
        }

    def build(**kwargs):
        captured.update(kwargs)
        return Result(status="needs_review")

    monkeypatch.setattr(
        "planning.successor_measurement.build_successor_plan",
        build,
    )

    ticks = iter([10.0, 12.5])

    measured = measure_successor_case(
        case=CASE,
        provider=Provider(),
        evidence_support_scorer=Scorer(),
        semantic_diversity_scorer=Scorer(),
        retrieve=retrieve,
        clock=lambda: next(ticks),
    )

    assert captured["detected_domain"] is None
    assert measured["detected_domain"] is None
    assert measured["elapsed_seconds"] == 2.5
    assert measured["status"] == "needs_review"
    assert measured["candidates"] == []


def test_ready_case_exposes_raw_candidates(monkeypatch):
    selected = [
        candidate("Incident Timeline"),
        candidate("Deployment Correlator"),
        candidate("Signal Investigation Workbench"),
    ]

    monkeypatch.setattr(
        "planning.successor_measurement.build_successor_plan",
        lambda **kwargs: Result(
            status="ready",
            candidates=selected,
            assessment={"status": "ready"},
        ),
    )

    ticks = iter([1.0, 2.0])

    measured = measure_successor_case(
        case=CASE,
        provider=Provider(),
        evidence_support_scorer=Scorer(),
        semantic_diversity_scorer=Scorer(),
        retrieve=lambda **kwargs: {
            "inference": {"inferred_focus": "cloud_platform"},
            "merged_results": [],
        },
        clock=lambda: next(ticks),
    )

    assert measured["status"] == "ready"
    assert len(measured["candidates"]) == 3
    assert measured["assessment"] == {"status": "ready"}


def test_non_ready_case_withholds_candidates(monkeypatch):
    monkeypatch.setattr(
        "planning.successor_measurement.build_successor_plan",
        lambda **kwargs: Result(
            status="needs_repair",
            candidates=[candidate("Hidden candidate")],
        ),
    )

    ticks = iter([1.0, 2.0])

    measured = measure_successor_case(
        case=CASE,
        provider=Provider(),
        evidence_support_scorer=Scorer(),
        semantic_diversity_scorer=Scorer(),
        retrieve=lambda **kwargs: {
            "inference": {"inferred_focus": "cloud_platform"},
            "merged_results": [],
        },
        clock=lambda: next(ticks),
    )

    assert measured["status"] == "needs_repair"
    assert measured["candidates"] == []


def test_report_uses_fresh_provider_per_case(monkeypatch):
    providers = []

    def factory():
        provider = Provider()
        providers.append(provider)
        return provider

    monkeypatch.setattr(
        "planning.successor_measurement.build_successor_plan",
        lambda **kwargs: Result(status="needs_review"),
    )

    ticks = iter([1.0, 2.0, 3.0, 5.0])

    report = build_successor_measurement_report(
        dataset={"cases": [CASE, {**CASE, "id": "incident-2"}]},
        provider_factory=factory,
        evidence_support_scorer=Scorer(),
        semantic_diversity_scorer=Scorer(),
        retrieve=lambda **kwargs: {
            "inference": {},
            "merged_results": [],
        },
        clock=lambda: next(ticks),
    )

    assert len(providers) == 2
    assert providers[0] is not providers[1]
    assert report["summary"]["case_count"] == 2
    assert report["summary"]["ready_count"] == 0
    assert report["summary"]["ready_rate"] == 0.0
    assert report["summary"]["status_counts"] == {
        "needs_review": 2
    }
    assert report["summary"]["total_tokens"] == 300
    assert report["summary"]["average_elapsed_seconds"] == 1.5


def test_report_tracks_ready_and_repair_rates(monkeypatch):
    statuses = iter(["ready", "needs_repair"])

    def build(**kwargs):
        status = next(statuses)
        return Result(
            status=status,
            candidates=(
                [
                    candidate("One"),
                    candidate("Two"),
                    candidate("Three"),
                ]
                if status == "ready"
                else []
            ),
        )

    monkeypatch.setattr(
        "planning.successor_measurement.build_successor_plan",
        build,
    )

    ticks = iter([1.0, 2.0, 3.0, 4.0])

    report = build_successor_measurement_report(
        dataset={"cases": [CASE, {**CASE, "id": "incident-2"}]},
        provider_factory=Provider,
        evidence_support_scorer=Scorer(),
        semantic_diversity_scorer=Scorer(),
        retrieve=lambda **kwargs: {
            "inference": {},
            "merged_results": [],
        },
        clock=lambda: next(ticks),
    )

    assert report["summary"]["ready_count"] == 1
    assert report["summary"]["ready_rate"] == 0.5
    assert report["summary"]["needs_repair_count"] == 1
    assert report["summary"]["status_counts"] == {
        "needs_repair": 1,
        "ready": 1,
    }
