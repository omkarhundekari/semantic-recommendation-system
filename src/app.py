import pandas as pd
import streamlit as st

from semantic_engine import SemanticEngine
from faiss_index import FaissIndex
from explainability import explain_recommendation
from hybrid_search import calculate_keyword_score, calculate_hybrid_score
from ui_helpers import display_result


st.set_page_config(
    page_title="Semantic Recommendation System",
    page_icon="🔎",
    layout="wide"
)

st.title("Semantic Recommendation and Retrieval System")
st.write(
    "Search documents using embeddings, FAISS vector search, keyword matching, "
    "hybrid ranking, and explainable results."
)

df = pd.read_csv("data/documents.csv")

st.sidebar.header("Filters")

available_categories = sorted(df["category"].unique())

selected_categories = st.sidebar.multiselect(
    "Select categories",
    available_categories,
    default=available_categories
)

semantic_weight = st.sidebar.slider(
    "Semantic weight",
    min_value=0.0,
    max_value=1.0,
    value=0.7,
    step=0.1
)

keyword_weight = 1.0 - semantic_weight

st.sidebar.write(f"Keyword weight: {keyword_weight:.1f}")

filtered_df = df[df["category"].isin(selected_categories)]
filtered_documents = filtered_df["content"].tolist()

engine = SemanticEngine()

query = st.text_input(
    "Enter your search query",
    "How do recommendation systems use graphs?"
)

top_k = st.slider(
    "Number of results",
    min_value=1,
    max_value=8,
    value=5
)

if st.button("Search"):

    if filtered_df.empty:
        st.warning("Please select at least one category.")
    else:
        document_embeddings = engine.create_embeddings(filtered_documents)
        query_embedding = engine.create_query_embedding(query)

        embedding_dimension = document_embeddings.shape[1]

        faiss_index = FaissIndex(embedding_dimension)
        faiss_index.build(document_embeddings)

        faiss_scores, faiss_indices = faiss_index.search(
            query_embedding,
            top_k=top_k
        )

        ranked_results = []

        for position, index in enumerate(faiss_indices):
            index = int(index)

            semantic_score = float(faiss_scores[position])

            keyword_score = calculate_keyword_score(
                query,
                filtered_documents[index]
            )

            hybrid_score = calculate_hybrid_score(
                semantic_score,
                keyword_score,
                semantic_weight=semantic_weight,
                keyword_weight=keyword_weight
            )

            ranked_results.append(
                {
                    "index": index,
                    "semantic_score": semantic_score,
                    "keyword_score": keyword_score,
                    "hybrid_score": hybrid_score
                }
            )

        ranked_results = sorted(
            ranked_results,
            key=lambda result: result["hybrid_score"],
            reverse=True
        )

        st.subheader("Search Results")

        for rank, result in enumerate(ranked_results, start=1):
            index = result["index"]

            explanation = explain_recommendation(
                selected_category="Search Query",
                recommended_category=filtered_df.iloc[index]["category"],
                similarity_score=result["semantic_score"]
            )

            display_result(
                rank=rank,
                title=filtered_df.iloc[index]["title"],
                category=filtered_df.iloc[index]["category"],
                score=result["hybrid_score"],
                content=filtered_df.iloc[index]["content"],
                explanation=(
                    f"{explanation} "
                    f"FAISS semantic score: {result['semantic_score']:.4f}, "
                    f"keyword score: {result['keyword_score']:.4f}, "
                    f"hybrid score: {result['hybrid_score']:.4f}."
                )
            )