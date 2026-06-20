from typing import Dict, List


class ProjectPlannerProvider:
    def generate(
        self,
        goal: str,
        constraints: Dict,
        evidence: List[Dict],
    ) -> Dict:
        raise NotImplementedError
