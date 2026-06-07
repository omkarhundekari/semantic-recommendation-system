import pandas as pd

from semantic_engine import SemanticEngine


# Load the dataset from CSV
df = pd.read_csv("data/documents.csv")

# Extract the content column as a list
documents = df["content"].tolist()

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

for rank, index in enumerate(top_results, start=1):
    index = int(index)

    score = similarity_scores[index].item()

    print(f"{rank}. {df.iloc[index]['title']}")
    print(f"Category: {df.iloc[index]['category']}")
    print(f"Similarity Score: {score:.4f}")
    print()