import sys
from pathlib import Path
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from plan_repair import repair_project_plan


class PlanRepairTests(unittest.TestCase):
    def test_short_timeline_is_narrowed(self):
        idea = {
            "project_title": "ML Prediction Monitoring Platform",
            "mvp_scope": [
                "Train a baseline model.",
                "Simulate inference batches.",
                "Track prediction quality.",
                "Detect drift.",
                "Show dashboards.",
                "Store monitoring runs.",
            ],
            "suggested_tech_stack": [
                "Python",
                "FastAPI",
                "Streamlit",
            ],
            "target_roles": ["ML Engineer"],
            "evidence_title": "Example evidence",
            "evidence_source_type": "project_pattern",
            "feasibility_analysis": {
                "build_profile": {
                    "estimated_effort": "8–12 days",
                }
            },
        }

        constraints = {
            "time_available": "1 week",
            "target_roles": ["ML Engineer"],
            "preferred_stack": ["Python"],
        }

        repaired, repairs, verification = repair_project_plan(
            idea,
            constraints,
        )

        profile = repaired["feasibility_analysis"]["build_profile"]

        self.assertEqual(profile["scope"], "Focused")
        self.assertEqual(profile["estimated_effort"], "3–5 days")
        self.assertIn(
            "Narrowed the MVP to fit a short timeline.",
            repairs,
        )
        self.assertNotIn(
            "Streamlit",
            repaired["suggested_tech_stack"],
        )
        self.assertEqual(verification["status"], "passed")


if __name__ == "__main__":
    unittest.main()
