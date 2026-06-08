import pandas as pd

from related_documents import RelatedDocuments


df = pd.read_csv("data/documents.csv")

related_engine = RelatedDocuments(df)

selected_title = "Graph Neural Networks for Recommendation Systems"

related_documents = related_engine.get_related_documents(
    title=selected_title,
    top_k=5
)

print("\nSelected Document:")
print(selected_title)

print("\nPeople Also Viewed / Related Documents:\n")

for rank, document in enumerate(related_documents, start=1):
    print(f"{rank}. {document['title']}")
    print(f"Category: {document['category']}")
    print(f"Similarity Score: {document['score']:.4f}")
    print()