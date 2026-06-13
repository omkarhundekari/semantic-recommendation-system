import pandas as pd

from semantic_engine import SemanticEngine


# Load the real arXiv research corpus
df = pd.read_csv("data/research_corpus.csv")

# Safety check: show dataset info
print(f"Loaded {len(df)} research papers")
print("Columns:", df.columns.tolist())

# Extract searchable text
# This assumes your real corpus has a 'content' column.
# If your column name is different, we will adjust after checking.
documents = df["content"].fillna("").tolist()

# User query
query = "How do recommendation systems use graphs?"

# Initialize the semantic search engine
engine = SemanticEngine()

# Convert documents into embeddings
document_embeddings = engine.create_embeddings(documents)

# Search for the most similar documents
top_results, similarity_scores = engine.search(
    query,
    documents,
    document_embeddings
)

print("\nUser Query:")
print(query)

print("\nTop Search Results:\n")

for rank, index in enumerate(top_results[:10], start=1):
    index = int(index)
    score = similarity_scores[index].item()

    title = df.iloc[index].get("title", "Untitled Paper")
    category = df.iloc[index].get("category", "Unknown Category")
    abstract = df.iloc[index].get("abstract", "")

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"Similarity Score: {score:.4f}")

    if isinstance(abstract, str) and abstract.strip():
        print(f"Abstract Preview: {abstract[:250]}...")

    print()