import sys
import pandas as pd

from semantic_engine import SemanticEngine


# Load the real arXiv research corpus
df = pd.read_csv("data/research_corpus.csv")

# Extract searchable text
documents = df["content"].fillna("").tolist()

# Initialize the semantic search engine
engine = SemanticEngine()

# Convert documents into embeddings
document_embeddings = engine.create_embeddings(documents)


def search_papers(query, top_k=5):
    """
    Search research papers using semantic similarity and return structured results.
    This function is used by the project idea generator.
    """

    top_results, similarity_scores = engine.search(
        query,
        documents,
        document_embeddings
    )

    results = []

    for index in top_results[:top_k]:
        index = int(index)
        score = similarity_scores[index].item()

        paper = df.iloc[index]

        results.append({
            "title": paper.get("title", "Untitled Paper"),
            "abstract": paper.get("content", ""),
            "content": paper.get("content", ""),
            "category": paper.get("category", "Unknown Category"),
            "authors": paper.get("authors", ""),
            "published": paper.get("published", ""),
            "url": paper.get("url", ""),
            "source": paper.get("source", ""),
            "score": float(score)
        })

    return results


if __name__ == "__main__":
    # Safety check: show dataset info only when running this file directly
    print(f"Loaded {len(df)} research papers")
    print("Columns:", df.columns.tolist())

    # User query
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "How do recommendation systems use graphs?"

    results = search_papers(query, top_k=10)

    print("\nUser Query:")
    print(query)

    print("\nTop Search Results:\n")

    for rank, result in enumerate(results, start=1):
        print(f"{rank}. {result['title']}")
        print(f"Category: {result['category']}")
        print(f"Similarity Score: {result['score']:.4f}")

        abstract = result.get("abstract", "")

        if isinstance(abstract, str) and abstract.strip():
            print(f"Abstract Preview: {abstract[:250]}...")

        print()