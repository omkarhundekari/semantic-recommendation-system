import streamlit as st


def display_result(rank, title, category, score, content, explanation=None):
    st.markdown(f"### {rank}. {title}")
    st.write(f"**Category:** {category}")
    st.write(f"**Similarity Score:** {score:.4f}")
    st.write(content)

    if explanation:
        st.info(explanation)

    st.divider()