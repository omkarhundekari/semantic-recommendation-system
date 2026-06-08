from cached_search import CachedSearch


cached_engine = CachedSearch()

query = "graph neural networks for recommendation systems"

scores, indices = cached_engine.search(
    query=query,
    top_k=5
)

print("\nSearch Results:\n")

for rank, (score, index) in enumerate(
        zip(scores, indices),
        start=1):

    title = cached_engine.df.iloc[index]["title"]
    category = cached_engine.df.iloc[index]["category"]

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"Score: {score:.4f}")
    print()