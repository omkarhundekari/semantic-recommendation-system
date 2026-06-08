import pandas as pd


categories = {
    "Recommendation Systems": [
        "Graph neural networks for recommendation systems",
        "Collaborative filtering using matrix factorization",
        "Session based recommendation with transformers",
        "Explainable recommendation using attention mechanisms",
        "Personalized ranking for e-commerce platforms",
    ],
    "Vector Search": [
        "FAISS for large scale vector retrieval",
        "Approximate nearest neighbor search using embeddings",
        "Vector databases for semantic search applications",
        "High dimensional similarity search in AI systems",
        "Embedding indexing for scalable retrieval",
    ],
    "RAG": [
        "Retrieval augmented generation for question answering",
        "Document retrieval for grounded language models",
        "RAG pipelines for enterprise knowledge systems",
        "Chunking strategies for retrieval augmented generation",
        "Evaluating retrieval quality in RAG systems",
    ],
    "NLP": [
        "Transformer models for natural language processing",
        "Sentence embeddings for semantic similarity",
        "Text classification using deep learning",
        "Named entity recognition with contextual embeddings",
        "Language model fine tuning for domain specific tasks",
    ],
    "Explainability": [
        "Explainable AI for recommendation engines",
        "Interpretable machine learning for search systems",
        "Feature attribution methods in neural networks",
        "Transparent ranking explanations for users",
        "Trustworthy AI through explanation generation",
    ],
    "Graph ML": [
        "Graph neural networks for knowledge graphs",
        "Graph embeddings for link prediction",
        "Node classification using graph convolutional networks",
        "Heterogeneous graphs for recommendation systems",
        "Graph based retrieval for structured knowledge",
    ],
    "Search": [
        "Hybrid search in modern AI applications",
        "Keyword and semantic search fusion",
        "Learning to rank for search engines",
        "Search relevance optimization using user feedback",
        "Query understanding for information retrieval",
    ],
    "MLOps": [
        "Model deployment pipelines for machine learning",
        "Monitoring embedding drift in production systems",
        "Feature stores for machine learning applications",
        "Continuous integration for ML systems",
        "Scalable model serving with FastAPI and Docker",
    ],
}


records = []
record_id = 1

for category, topics in categories.items():
    for topic in topics:
        for version in range(1, 26):
            title = f"{topic.title()} Study {version}"

            content = (
                f"This document discusses {topic}. "
                f"It focuses on {category.lower()} and explains core methods, "
                f"system design ideas, mathematical intuition, evaluation strategies, "
                f"and practical implementation challenges in modern AI systems."
            )

            records.append(
                {
                    "id": record_id,
                    "title": title,
                    "category": category,
                    "content": content
                }
            )

            record_id += 1


df = pd.DataFrame(records)

df.to_csv("data/large_documents.csv", index=False)

print("Large dataset created successfully.")
print(f"Total records: {len(df)}")
print("Saved to: data/large_documents.csv")