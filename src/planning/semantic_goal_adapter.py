from typing import Any

from planning.semantic_goal_relevance import (
    EmbeddingVector,
    TextEncoder,
)


class SemanticEngineTextEncoder(TextEncoder):
    """
    Adapts an existing SemanticEngine instance for planning-only scoring.

    The adapter does not construct SemanticEngine itself, so importing this
    module never loads a model. A caller creates SemanticEngine once and
    injects that instance when semantic shadow scoring is enabled.
    """

    def __init__(self, semantic_engine: Any):
        self._semantic_engine = semantic_engine

    def encode_text(self, text: str) -> EmbeddingVector:
        embedding = self._semantic_engine.create_query_embedding(text)

        if hasattr(embedding, "detach"):
            embedding = embedding.detach()

        if hasattr(embedding, "cpu"):
            embedding = embedding.cpu()

        if hasattr(embedding, "tolist"):
            values = embedding.tolist()
        else:
            values = list(embedding)

        if values and isinstance(values[0], (list, tuple)):
            values = values[0]

        return EmbeddingVector(
            values=tuple(float(value) for value in values)
        )
