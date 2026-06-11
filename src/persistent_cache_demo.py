from persistent_cache import PersistentCache

cache = PersistentCache()

query = "retrieval augmented generation for question answering"

scores, indices = cache.search(
    query=query,
    top_k=5
)

print("\nSearch Results:\n")

for rank, (score, index) in enumerate(
        zip(scores, indices),
        start=1):

    title = cache.df.iloc[index]["title"]
    category = cache.df.iloc[index]["category"]

    print(f"{rank}. {title}")
    print(f"Category: {category}")
    print(f"Score: {score:.4f}")
    print()