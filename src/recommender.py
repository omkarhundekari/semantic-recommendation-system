import pandas as pd

from semantic_engine import SemanticEngine
from explainability import explain_recommendation


df = pd.read_csv("data/documents.csv")

documents = df["content"].tolist()

engine = SemanticEngine()

document_embeddings = engine.create_embeddings(documents)

selected_title = "Graph Neural Networks for Recommendation Systems"

matching_rows = df[df["title"].str.lower() == selected_title.lower()]

if matching_rows.empty:
    print("Document not found.")
else:
    selected_index = matching_rows.index[0]
    selected_content = df.iloc[selected_index]["content"]
    selected_category = df.iloc[selected_index]["category"]

    top_results, similarity_scores = engine.search(
        selected_content,
        documents,
        document_embeddings
    )

    print(f"\nSelected Document:")
    print(selected_title)

    print("\nRecommended Similar Documents:\n")

    display_rank = 1

    for index in top_results:
        index = int(index)

        if index == selected_index:
            continue

        score = similarity_scores[index].item()
        recommended_category = df.iloc[index]["category"]

        explanation = explain_recommendation(
            selected_category,
            recommended_category,
            score
        )

        print(f"{display_rank}. {df.iloc[index]['title']}")
        print(f"Category: {recommended_category}")
        print(f"Similarity Score: {score:.4f}")
        print(f"Explanation: {explanation}")
        print()

        display_rank += 1