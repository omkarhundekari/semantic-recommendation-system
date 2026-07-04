import unittest

from query_understanding import understand_query


class QueryUnderstandingTests(unittest.TestCase):
    def test_detailed_ml_goal_does_not_require_early_clarification(self):
        result = understand_query(
            goal=(
                "I want to build an AI/ML project for an ML Engineer role. "
                "I know Python and have three weeks."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["ML Engineer"],
                "preferred_stack": ["Python"],
            },
        )

        self.assertFalse(
            result["requires_clarification_before_retrieval"]
        )
        self.assertIn("ai_ml", result["direction_hints"])

    def test_security_goal_extracts_security_direction(self):
        result = understand_query(
            goal=(
                "I want to build a cybersecurity automation project "
                "for a security analyst role."
            )
        )

        self.assertFalse(
            result["requires_clarification_before_retrieval"]
        )
        self.assertIn("cybersecurity", result["direction_hints"])

    def test_vague_resume_goal_requires_early_clarification(self):
        result = understand_query(
            goal="I want to build something useful for my resume."
        )

        self.assertTrue(
            result["requires_clarification_before_retrieval"]
        )
        self.assertEqual(
            result["clarification_question"],
            "What kind of work would you like this project to showcase?",
        )
        self.assertIn(
            "AI / ML",
            result["clarification_options"],
        )

    def test_short_unclear_goal_requires_early_clarification(self):
        result = understand_query(goal="Need a good project")

        self.assertTrue(
            result["requires_clarification_before_retrieval"]
        )


    def test_developer_productivity_goal_extracts_software_engineering_hint(
        self,
    ):
        result = understand_query(
            goal=(
                "Build a developer productivity project that helps engineers "
                "identify flaky tests, connect failures with code changes, "
                "and prioritize likely root causes."
            )
        )

        self.assertIn(
            "software_engineering",
            result["direction_hints"],
        )


if __name__ == "__main__":
    unittest.main()
