import pandas as pd

from fastapi import FastAPI
from pydantic import BaseModel

from src.semantic_engine import SemanticEngine
from src.faiss_index import FaissIndex
from src.hybrid_search import calculate_keyword_score, calculate_hybrid_score
from src.explainability import explain_recommendation


app = FastAPI(
    title="Semantic Recommendation and Retrieval API",
    description="Hybrid semantic search API using embeddings, FAISS, keyword matching, and explainable ranking.",
    version="1.0.0"
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    semantic_weight: float = 0.7


df = pd.read_csv("data/documents.csv")
documents = df["content"].tolist()

engine = SemanticEngine()
document_embeddings = engine.create_embeddings(documents)

embedding_dimension = document_embeddings.shape[1]

faiss_index = FaissIndex(embedding_dimension)
faiss_index.build(document_embeddings)


@app.get("/")
def home():
    return {
        "message": "Semantic Recommendation and Retrieval API is running."
    }


@app.post("/search")
def search_documents(request: SearchRequest):
    query_embedding = engine.create_query_embedding(request.query)

    faiss_scores, faiss_indices = faiss_index.search(
        query_embedding,
        top_k=request.top_k
    )

    keyword_weight = 1.0 - request.semantic_weight

    results = []

    for position, index in enumerate(faiss_indices):
        index = int(index)

        semantic_score = float(faiss_scores[position])

        keyword_score = calculate_keyword_score(
            request.query,
            documents[index]
        )

        hybrid_score = calculate_hybrid_score(
            semantic_score,
            keyword_score,
            semantic_weight=request.semantic_weight,
            keyword_weight=keyword_weight
        )

        explanation = explain_recommendation(
            selected_category="Search Query",
            recommended_category=df.iloc[index]["category"],
            similarity_score=semantic_score
        )

        results.append(
            {
                "rank": position + 1,
                "title": df.iloc[index]["title"],
                "category": df.iloc[index]["category"],
                "content": df.iloc[index]["content"],
                "semantic_score": round(semantic_score, 4),
                "keyword_score": round(keyword_score, 4),
                "hybrid_score": round(hybrid_score, 4),
                "explanation": explanation
            }
        )

    results = sorted(
        results,
        key=lambda result: result["hybrid_score"],
        reverse=True
    )

    return {
        "query": request.query,
        "top_k": request.top_k,
        "semantic_weight": request.semantic_weight,
        "keyword_weight": round(keyword_weight, 2),
        "results": results
    }