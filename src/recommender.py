import sys
import pandas as pd

from semantic_engine import SemanticEngine
from explainability import explain_recommendation


# Load the real arXiv research corpus
df = pd.read_csv("data/research_corpus.csv")

print(f"Loaded {len(df)} research papers")

# Prepare searchable paper content
documents = df["content"].fillna("").tolist()

# Initialize semantic engine
engine = SemanticEngine()

# Create embeddings for all papers
document_embeddings = engine.create_embeddings(documents)

# Accept selected paper title from command line
if len(sys.argv) > 1:
    selected_title = " ".join(sys.argv[1:])
else:
    selected_title = "Graph Neural Networks in Recommender Systems: A Survey"

# Try exact title match first
matching_rows = df[df["title"].str.lower() == selected_title.lower()]

# If exact title is not found, use semantic search to find the closest paper title/content
if matching_rows.empty:
    print("\nExact paper title not found.")
    print("Searching for the closest matching paper...\n")

    candidate_results, candidate_scores = engine.search(
        selected_title,
        documents,
        document_embeddings
    )

    selected_index = int(candidate_results[0])
    selected_title = df.iloc[selected_index]["title"]
else:
    selected_index = matching_rows.index[0]

selected_content = df.iloc[selected_index]["content"]
selected_category = df.iloc[selected_index]["category"]

# Recommend papers similar to the selected paper content
top_results, similarity_scores = engine.search(
    selected_content,
    documents,
    document_embeddings
)

print("\nSelected Paper:")
print(selected_title)
print(f"Category: {selected_category}")

print("\nRecommended Similar Papers:\n")

display_rank = 1

for index in top_results:
    index = int(index)

    # Skip the selected paper itself
    if index == selected_index:
        continue

    score = similarity_scores[index].item()
    recommended_title = df.iloc[index].get("title", "Untitled Paper")
    recommended_category = df.iloc[index].get("category", "Unknown Category")
    recommended_url = df.iloc[index].get("url", "")

    explanation = explain_recommendation(
        selected_category,
        recommended_category,
        score,
        selected_title,
        recommended_title
    )

    print(f"{display_rank}. {recommended_title}")
    print(f"Category: {recommended_category}")
    print(f"Similarity Score: {score:.4f}")
    print(f"Explanation: {explanation}")

    if isinstance(recommended_url, str) and recommended_url.strip():
        print(f"URL: {recommended_url}")

    print()

    display_rank += 1

    if display_rank > 10:
        break