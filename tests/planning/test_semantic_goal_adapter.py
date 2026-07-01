from planning.semantic_goal_adapter import SemanticEngineTextEncoder


class FakeTensor:
    def __init__(self, values):
        self._values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self._values


class FakeSemanticEngine:
    def __init__(self):
        self.requests = []

    def create_query_embedding(self, text):
        self.requests.append(text)
        return FakeTensor([[0.25, 0.75]])


def test_adapter_wraps_existing_semantic_engine_output():
    engine = FakeSemanticEngine()
    encoder = SemanticEngineTextEncoder(engine)

    vector = encoder.encode_text("planning goal")

    assert engine.requests == ["planning goal"]
    assert vector.values == (0.25, 0.75)
