import sys
from pathlib import Path
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from plan_verifier import verify_project_ideas


CONSTRAINTS = {
    "time_available": "1 week",
    "target_roles": ["ML Engineer"],
    "preferred_stack": ["Python"],
}


def build_valid_idea(title="ML Prediction Monitoring Platform"):
    return {
        "project_title": title,
        "idea_angle": "Monitor drift and prediction quality for a deployed ML model.",
        "research_motivation": "Grounded in a project pattern and implementation evidence.",
        "mvp_scope": [
            "Train one baseline model using a public dataset.",
            "Simulate timestamped inference batches.",
            "Track prediction quality and feature distributions.",
            "Detect simple prediction drift with transparent thresholds.",
            "Show alerts and trend charts in a dashboard.",
            "Store monitoring runs for comparison.",
        ],
        "suggested_tech_stack": [
            "Python",
            "FastAPI",
            "PostgreSQL",
            "Docker",
            "React",
        ],
        "target_roles": ["ML Engineer", "AI Engineer"],
        "evidence_title": "Example evidence",
        "evidence_source_type": "github_repository",
        "feasibility_analysis": {
            "build_profile": {
                "estimated_effort": "5–8 days",
            }
        },
    }


class PlanVerifierTests(unittest.TestCase):
    def test_valid_plan_passes(self):
        valid_constraints = {
            **CONSTRAINTS,
            "time_available": "2 weeks",
        }

        result = verify_project_ideas(
            [build_valid_idea()],
            valid_constraints,
        )[0]

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["score"], result["max_score"])

    def test_missing_evidence_is_flagged(self):
        idea = build_valid_idea()
        idea["evidence_title"] = ""
        idea["evidence_source_type"] = ""

        result = verify_project_ideas([idea], CONSTRAINTS)[0]

        self.assertFalse(result["checks"]["evidence_present"])
        self.assertIn(
            "The direction has no visible evidence reference.",
            result["warnings"],
        )

    def test_streamlit_is_flagged(self):
        idea = build_valid_idea()
        idea["suggested_tech_stack"].append("Streamlit")

        result = verify_project_ideas([idea], CONSTRAINTS)[0]

        self.assertFalse(result["checks"]["no_banned_stack"])

    def test_generic_mvp_language_is_flagged(self):
        idea = build_valid_idea()
        idea["mvp_scope"] = [
            "Build a simple input form for the user.",
            "Store project data in a CSV-backed prototype.",
        ]

        result = verify_project_ideas([idea], CONSTRAINTS)[0]

        self.assertFalse(result["checks"]["specific_mvp_language"])

    def test_one_week_timeline_rejects_large_plan(self):
        idea = build_valid_idea()
        idea["feasibility_analysis"]["build_profile"][
            "estimated_effort"
        ] = "8–12 days"

        result = verify_project_ideas([idea], CONSTRAINTS)[0]

        self.assertFalse(result["checks"]["time_feasibility"])

    def test_duplicate_titles_are_flagged(self):
        first = build_valid_idea()
        second = build_valid_idea()

        results = verify_project_ideas(
            [first, second],
            CONSTRAINTS,
        )

        self.assertFalse(results[0]["checks"]["direction_is_distinct"])
        self.assertFalse(results[1]["checks"]["direction_is_distinct"])


if __name__ == "__main__":
    unittest.main()
