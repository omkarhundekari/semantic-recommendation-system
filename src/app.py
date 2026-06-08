import pandas as pd
import streamlit as st



from explainability import explain_recommendation
from hybrid_search import calculate_keyword_score, calculate_hybrid_score
from related_documents import RelatedDocuments
from embedding_visualization import create_embedding_map
from interactive_visualization import create_interactive_embedding_plot
from ui_helpers import display_result
from analytics import log_query, log_feedback
from persistent_cache import PersistentCache


st.set_page_config(
    page_title="Semantic Recommendation System",
    page_icon="🔎",
    layout="wide"
)

st.title("Semantic Recommendation and Retrieval System")
st.write(
    "Search documents using embeddings, FAISS vector search, keyword matching, "
    "hybrid ranking, explainability, related recommendations, interactive visualization, "
    "and user feedback."
)

df = pd.read_csv("data/large_documents.csv")


@st.cache_resource
def load_cached_engine():
    return PersistentCache()

cached_engine = load_cached_engine()

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

top_k = st.slider(
    "Number of results",
    min_value=1,
    max_value=8,
    value=5
)

show_related = st.checkbox("Show related documents", value=True)
show_embedding_map = st.checkbox("Show embedding map", value=True)

if st.button("Search"):
    log_query(query)

    if filtered_df.empty:
        st.warning("Please select at least one category.")
        st.session_state.search_results = []

    else:
        faiss_scores, faiss_indices = cached_engine.search(
            query=query,
            top_k=top_k
        )

        if show_embedding_map:
            st.session_state.embedding_map_df = create_embedding_map(
                cached_engine.document_embeddings,
                cached_engine.df
            )

        ranked_results = []

        for position, index in enumerate(faiss_indices):
            index = int(index)

            semantic_score = float(faiss_scores[position])

            keyword_score = calculate_keyword_score(
                query,
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
                    "title": cached_engine.df.iloc[index]["title"],
                    "category": cached_engine.df.iloc[index]["category"],
                    "content": cached_engine.df.iloc[index]["content"],
                    "semantic_score": semantic_score,
                    "keyword_score": keyword_score,
                    "hybrid_score": hybrid_score
                }
            )

        st.session_state.search_results = sorted(
            ranked_results,
            key=lambda result: result["hybrid_score"],
            reverse=True
        )

if show_embedding_map and st.session_state.embedding_map_df is not None:
    st.subheader("Interactive Embedding Map")
    fig = create_interactive_embedding_plot(st.session_state.embedding_map_df)
    st.plotly_chart(fig, use_container_width=True)

if st.session_state.search_results:
    st.subheader("Search Results")

    related_engine = RelatedDocuments(cached_engine.df)

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