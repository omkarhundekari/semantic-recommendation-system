from typing import Dict, List

from llm.provider import ProjectPlannerProvider


class MockProjectPlannerProvider(ProjectPlannerProvider):
    """
    Local development placeholder.

    This intentionally does not pretend to be an LLM. It formats the
    existing deterministic planning output into the same future provider
    interface that OpenAI or another model will later implement.
    """

    def generate(
        self,
        goal: str,
        constraints: Dict,
        evidence: List[Dict],
    ) -> Dict:
        return {
            "provider": "mock",
            "model": "deterministic-development-mode",
            "goal": goal,
            "constraints_used": {
                "skill_level": constraints.get("skill_level"),
                "time_available": constraints.get("time_available"),
                "target_roles": constraints.get("target_roles", []),
                "preferred_stack": constraints.get("preferred_stack", []),
            },
            "evidence_count": len(evidence),
        }
