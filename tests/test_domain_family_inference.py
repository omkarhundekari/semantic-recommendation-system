import unittest

from domain_taxonomy import (
    get_domain_family,
    get_family_focuses,
    get_focus_from_category,
    is_focus_in_family,
)


class DomainTaxonomyTests(unittest.TestCase):
    def test_ai_ml_related_focuses_share_ai_ml_family(self):
        focuses = [
            "ai_ml",
            "mlops",
            "rag_llm",
            "nlp",
            "computer_vision",
            "healthcare_ai",
            "recommendation_systems",
        ]

        for focus in focuses:
            self.assertEqual(
                get_domain_family(focus),
                "ai_ml",
            )

    def test_software_engineering_related_focuses_share_family(self):
        focuses = [
            "frontend",
            "backend",
            "full_stack",
            "developer_tools",
            "mobile",
        ]

        for focus in focuses:
            self.assertEqual(
                get_domain_family(focus),
                "software_engineering",
            )

    def test_cloud_platform_related_focuses_share_family(self):
        focuses = [
            "cloud",
            "devops",
            "data_engineering",
            "databases",
        ]

        for focus in focuses:
            self.assertEqual(
                get_domain_family(focus),
                "cloud_platform",
            )

    def test_arxiv_software_engineering_maps_to_developer_tools(self):
        self.assertEqual(
            get_focus_from_category("cs.SE"),
            "developer_tools",
        )

    def test_unknown_focus_defaults_to_general(self):
        self.assertEqual(
            get_domain_family("something_unknown"),
            "general",
        )

    def test_family_focus_lookup(self):
        focuses = get_family_focuses("ai_ml")

        self.assertIn("ai_ml", focuses)
        self.assertIn("mlops", focuses)
        self.assertIn("healthcare_ai", focuses)

    def test_focus_membership_check(self):
        self.assertTrue(
            is_focus_in_family("frontend", "software_engineering")
        )

        self.assertFalse(
            is_focus_in_family("cloud", "software_engineering")
        )


if __name__ == "__main__":
    unittest.main()
