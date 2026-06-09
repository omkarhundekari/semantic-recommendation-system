import pandas as pd
import streamlit as st

from fuzzy_search import get_query_suggestions, get_best_query_correction
from explainability import explain_recommendation
from hybrid_search import calculate_keyword_score, calculate_hybrid_score
from related_documents import RelatedDocuments
from embedding_visualization import create_embedding_map
from interactive_visualization import create_interactive_embedding_plot
from ui_helpers import display_result
from analytics import log_query, log_feedback
from rrf_fusion import reciprocal_rank_fusion


st.set_page_config(
    page_title="Semantic Recommendation System",
    page_icon="🔎",
    layout="wide"
)


@st.cache_data
def load_documents():
    return pd.read_csv("data/large_documents.csv")


@st.cache_resource
def load_cached_engine():
    from persistent_cache import PersistentCache
    return PersistentCache()


@st.cache_resource
def load_bm25(documents_tuple):
    from bm25_retriever import BM25Retriever
    return BM25Retriever(list(documents_tuple))


@st.cache_resource
def load_reranker():
    from reranker import CrossEncoderReranker
    return CrossEncoderReranker()


st.title("Semantic Recommendation and Retrieval System")
st.write(
    "Search documents using FAISS, BM25, RRF fusion, CrossEncoder reranking, "
    "explainability, related recommendations, and feedback."
)

df = load_documents()

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "embedding_map_df" not in st.session_state:
    st.session_state.embedding_map_df = None

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

query = st.text_input(
    "Enter your search query",
    "How do recommendation systems use graphs?"
)

if query.strip():
    suggestions = get_query_suggestions(
        query=query,
        titles=df["title"].tolist(),
        limit=5
    )

    if suggestions:
        with st.expander("Query suggestions"):
            for item in suggestions:
                st.write(f"{item['suggestion']} — score: {item['score']:.2f}")

top_k = st.slider(
    "Number of results",
    min_value=1,
    max_value=8,
    value=5
)

show_related = st.checkbox("Show related documents", value=True)
show_embedding_map = st.checkbox("Show embedding map", value=True)
use_rrf = st.checkbox("Use RRF fusion", value=True)
use_reranker = st.checkbox("Use CrossEncoder reranking", value=False)

if st.button("Search"):
    log_query(query)

    corrected_query = get_best_query_correction(
        query=query,
        titles=df["title"].tolist(),
        minimum_score=60
    )

    if corrected_query != query:
        st.info(f"Searching instead for: {corrected_query}")

    if filtered_df.empty:
        st.warning("Please select at least one category.")
        st.session_state.search_results = []

    else:
        with st.spinner("Loading persistent FAISS cache..."):
            cached_engine = load_cached_engine()

        with st.spinner("Running FAISS retrieval..."):
            faiss_scores, faiss_indices = cached_engine.search_by_categories(
                query=corrected_query,
                selected_categories=selected_categories,
                top_k=20
            )

        faiss_ranked = [
            {
                "index": int(index),
                "score": float(score)
            }
            for score, index in zip(faiss_scores, faiss_indices)
        ]

        if use_rrf:
            with st.spinner("Running BM25 + RRF fusion..."):
                bm25_retriever = load_bm25(tuple(cached_engine.documents))

                bm25_ranked_all = bm25_retriever.search(
                    query=corrected_query,
                    top_k=100
                )

                selected_category_set = set(selected_categories)

                bm25_ranked = [
                    item
                    for item in bm25_ranked_all
                    if df.iloc[item["index"]]["category"] in selected_category_set
                ][:20]

                fused_results = reciprocal_rank_fusion(
                    rank_lists=[faiss_ranked, bm25_ranked],
                    k=60
                )

                candidate_indices = [
                    result["index"]
                    for result in fused_results[:20]
                ]

        else:
            candidate_indices = [
                result["index"]
                for result in faiss_ranked
            ]

        if show_embedding_map:
            selected_indices = filtered_df.index.tolist()

            filtered_embeddings = cached_engine.document_embeddings[selected_indices]

            st.session_state.embedding_map_df = create_embedding_map(
                filtered_embeddings,
                filtered_df
            )

        ranked_results = []

        for index in candidate_indices:
            index = int(index)

            semantic_score = 0.0

            for item in faiss_ranked:
                if item["index"] == index:
                    semantic_score = item["score"]
                    break

            keyword_score = calculate_keyword_score(
                corrected_query,
                cached_engine.documents[index]
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
                    "title": df.iloc[index]["title"],
                    "category": df.iloc[index]["category"],
                    "content": df.iloc[index]["content"],
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

        if use_reranker:
            with st.spinner("Running CrossEncoder reranking..."):
                reranker = load_reranker()

                ranked_results = reranker.rerank(
                    query=corrected_query,
                    documents=ranked_results
                )

        st.session_state.search_results = ranked_results[:top_k]

if show_embedding_map and st.session_state.embedding_map_df is not None:
    st.subheader("Interactive Embedding Map")
    fig = create_interactive_embedding_plot(st.session_state.embedding_map_df)
    st.plotly_chart(fig, use_container_width=True)

if st.session_state.search_results:
    st.subheader("Search Results")

    related_engine = RelatedDocuments(df)

    for rank, result in enumerate(st.session_state.search_results, start=1):
        title = result["title"]
        category = result["category"]
        content = result["content"]

        explanation = explain_recommendation(
            selected_category="Search Query",
            recommended_category=category,
            similarity_score=result["semantic_score"]
        )

        display_result(
            rank=rank,
            title=title,
            category=category,
            score=result["hybrid_score"],
            content=content,
            explanation=(
                f"{explanation} "
                f"FAISS semantic score: {result['semantic_score']:.4f}, "
                f"keyword score: {result['keyword_score']:.4f}, "
                f"hybrid score: {result['hybrid_score']:.4f}."
            )
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Helpful 👍", key=f"helpful_{rank}_{title}"):
                log_feedback(title, "helpful")
                st.success("Helpful feedback saved.")

        with col2:
            if st.button("Not helpful 👎", key=f"not_helpful_{rank}_{title}"):
                log_feedback(title, "not_helpful")
                st.warning("Not helpful feedback saved.")

        if show_related:
            related_docs = related_engine.get_related_documents(
                title=title,
                top_k=3
            )

            with st.expander("People also viewed / Related documents"):
                for related_doc in related_docs:
                    st.write(f"**{related_doc['title']}**")
                    st.write(f"Category: {related_doc['category']}")
                    st.write(f"Similarity Score: {related_doc['score']:.4f}")
                    st.write("---")