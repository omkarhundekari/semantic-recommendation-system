import pandas as pd

from fuzzy_search import get_query_suggestions


df = pd.read_csv("data/large_documents.csv")

titles = df["title"].tolist()

query = "grph nueral netwrks"

suggestions = get_query_suggestions(
    query=query,
    titles=titles,
    limit=5
)

print("\nUser typed:")
print(query)

print("\nQuery Suggestions:\n")

for rank, item in enumerate(suggestions, start=1):
    print(f"{rank}. {item['suggestion']}")
    print(f"Match Score: {item['score']}")
    print()