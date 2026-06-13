import sys
import pandas as pd

from semantic_engine import SemanticEngine
from hybrid_search import calculate_keyword_score, calculate_hybrid_score


df = pd.read_csv("data/research_corpus.csv")
documents = df["content"].fillna("").tolist()

query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "retrieval augmented generation for question answering"

engine = SemanticEngine()
document_embeddings = engine.create_embeddings(documents)

top_results, similarity_scores = engine.search(
    query,
    documents,
    document_embeddings
)

hybrid_results = []

for index in top_results[:50]:
    index = int(index)

    semantic_score = similarity_scores[index].item()
    keyword_score = calculate_keyword_score(query, documents[index])
    hybrid_score = calculate_hybrid_score(semantic_score, keyword_score)

    hybrid_results.append({
        "index": index,
        "semantic_score": semantic_score,
        "keyword_score": keyword_score,
        "hybrid_score": hybrid_score
    })

hybrid_results = sorted(
    hybrid_results,
    key=lambda item: item["hybrid_score"],
    reverse=True
)

print(f"\nLoaded {len(df)} research papers")

print("\nUser Query:")
print(query)

print("\nTop Hybrid Search Results:\n")

for rank, result in enumerate(hybrid_results[:10], start=1):
    index = result["index"]

    title = df.iloc[index].get("title", "Untitled Paper")
    category = df.iloc[index].get("category", "Unknown Category")
    url = df.iloc[index].get("url", "")

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"Semantic Score: {result['semantic_score']:.4f}")
    print(f"Keyword Score: {result['keyword_score']:.4f}")
    print(f"Hybrid Score: {result['hybrid_score']:.4f}")

    if isinstance(url, str) and url.strip():
        print(f"URL: {url}")

    print()