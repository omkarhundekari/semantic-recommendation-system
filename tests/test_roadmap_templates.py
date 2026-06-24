import unittest

from roadmap_templates import get_domain_mvp_template


class RoadmapTemplateTests(unittest.TestCase):
    def test_security_template_is_specific(self):
        steps = get_domain_mvp_template(
            "Security Vulnerability Prioritization Engine",
            "cybersecurity",
        )

        text = " ".join(steps).lower()

        self.assertIn("vulnerability", text)
        self.assertIn("risk", text)
        self.assertNotIn("user query or project data", text)

    def test_cloud_risk_scanner_is_specific(self):
        steps = get_domain_mvp_template(
            "Cloud Resource Risk Scanner",
            "cloud",
        )

        text = " ".join(steps).lower()

        self.assertIn("iam", text)
        self.assertIn("misconfigured", text)

    def test_serverless_observability_is_specific(self):
        steps = get_domain_mvp_template(
            "Serverless Observability Platform",
            "cloud",
        )

        text = " ".join(steps).lower()

        self.assertIn("cold-start", text)
        self.assertIn("function", text)

    def test_frontend_template_is_specific(self):
        steps = get_domain_mvp_template(
            "Frontend Architecture Intelligence Platform",
            "frontend",
        )

        text = " ".join(steps).lower()

        self.assertIn("component", text)
        self.assertIn("repository", text)


if __name__ == "__main__":
    unittest.main()
