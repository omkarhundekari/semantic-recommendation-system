import unittest

from evidence_domain_inference import infer_domain_from_evidence


def make_item(title, category, source_type, score):
    return {
        "title": title,
        "category": category,
        "source_type": source_type,
        "score": score,
    }


class EvidenceDomainInferenceTests(unittest.TestCase):
    def test_ai_ml_evidence_is_detected(self):
        evidence = [
            make_item(
                "Machine Learning Model Evaluation",
                "cs.LG",
                "research_paper",
                0.90,
            ),
            make_item(
                "Model Monitoring Dashboard",
                "ai_ml",
                "project_pattern",
                0.85,
            ),
            make_item(
                "Experiment Tracking Platform",
                "mlops",
                "github_repository",
                0.80,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertEqual(
            result["inferred_domain_family"],
            "ai_ml",
        )
        self.assertEqual(
            result["inferred_focus"],
            "ai_ml",
        )
        self.assertFalse(result["requires_clarification"])

    def test_frontend_evidence_is_detected(self):
        evidence = [
            make_item(
                "React Analytics Dashboard",
                "frontend",
                "project_pattern",
                0.90,
            ),
            make_item(
                "Modern Frontend Architecture",
                "frontend",
                "research_paper",
                0.80,
            ),
            make_item(
                "React Component Library",
                "frontend",
                "github_repository",
                0.86,
            ),
            make_item(
                "Full Stack Product Dashboard",
                "full_stack",
                "project_pattern",
                0.70,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertEqual(
            result["inferred_domain_family"],
            "software_engineering",
        )
        self.assertEqual(
            result["inferred_focus"],
            "frontend",
        )
        self.assertFalse(result["requires_clarification"])

    def test_cloud_evidence_is_detected(self):
        evidence = [
            make_item(
                "Cloud Cost Optimization",
                "cloud",
                "project_pattern",
                0.92,
            ),
            make_item(
                "Cloud Resource Allocation",
                "cloud",
                "research_paper",
                0.84,
            ),
            make_item(
                "Infrastructure Automation",
                "devops",
                "github_repository",
                0.78,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertEqual(
            result["inferred_domain_family"],
            "cloud_platform",
        )
        self.assertEqual(
            result["inferred_focus"],
            "cloud",
        )
        self.assertFalse(result["requires_clarification"])

    def test_security_evidence_is_detected(self):
        evidence = [
            make_item(
                "Security Incident Automation",
                "cybersecurity",
                "project_pattern",
                0.91,
            ),
            make_item(
                "Threat Detection Workflow",
                "security",
                "research_paper",
                0.84,
            ),
            make_item(
                "Security Alert Automation",
                "cybersecurity",
                "github_repository",
                0.80,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertEqual(
            result["inferred_domain_family"],
            "cybersecurity",
        )
        self.assertEqual(
            result["inferred_focus"],
            "cybersecurity",
        )
        self.assertFalse(result["requires_clarification"])

    def test_ambiguous_evidence_requires_clarification(self):
        evidence = [
            make_item(
                "Generic Resume Project",
                "frontend",
                "project_pattern",
                0.70,
            ),
            make_item(
                "Cloud Learning Tool",
                "cloud",
                "github_repository",
                0.69,
            ),
            make_item(
                "Basic AI Application",
                "ai_ml",
                "research_paper",
                0.68,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertTrue(result["requires_clarification"])

    def test_unknown_categories_require_clarification(self):
        evidence = [
            make_item(
                "Uncategorized Project",
                "unknown_topic",
                "project_pattern",
                0.80,
            ),
            make_item(
                "Another Uncategorized Result",
                "",
                "research_paper",
                0.75,
            ),
        ]

        result = infer_domain_from_evidence(evidence)

        self.assertEqual(
            result["inferred_domain_family"],
            "general",
        )
        self.assertTrue(result["requires_clarification"])


if __name__ == "__main__":
    unittest.main()

def test_explicit_focus_with_some_evidence_resolves_family_ambiguity():
    evidence_items = [
        {
            "title": "Developer tool paper",
            "category": "developer_tools",
            "source_type": "research_paper",
        },
        {
            "title": "Repository analytics implementation",
            "category": "developer_tools",
            "source_type": "github_repository",
        },
        {
            "title": "DevOps observability project pattern",
            "category": "devops",
            "source_type": "project_pattern",
        },
        {
            "title": "Cloud monitoring repository",
            "category": "cloud",
            "source_type": "github_repository",
        },
    ]

    result = infer_domain_from_evidence(
        evidence_items,
        intent_hints=["cloud_platform", "devops"],
    )

    assert result["inferred_domain_family"] == "cloud_platform"
    assert result["inferred_focus"] in {"cloud", "devops"}
    assert result["requires_clarification"] is False


def test_explicit_focus_with_some_evidence_resolves_family_ambiguity():
    evidence_items = [
        {
            "title": "Developer tool paper",
            "category": "developer_tools",
            "source_type": "research_paper",
        },
        {
            "title": "Repository analytics implementation",
            "category": "developer_tools",
            "source_type": "github_repository",
        },
        {
            "title": "DevOps observability project pattern",
            "category": "devops",
            "source_type": "project_pattern",
        },
        {
            "title": "Cloud monitoring repository",
            "category": "cloud",
            "source_type": "github_repository",
        },
    ]

    result = infer_domain_from_evidence(
        evidence_items,
        intent_hints=["cloud_platform", "devops"],
    )

    assert result["inferred_domain_family"] == "cloud_platform"
    assert result["requires_clarification"] is False
