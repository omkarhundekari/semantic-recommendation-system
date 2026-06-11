from urllib.parse import quote_plus
import time

import feedparser
import pandas as pd


TOPICS = [
    "retrieval augmented generation",
    "graph retrieval augmented generation",
    "semantic search",
    "information retrieval",
    "vector databases",
    "recommendation systems",
    "graph neural networks recommendation",
    "knowledge graphs",
    "large language model agents",
    "neural reranking",
    "learning to rank",
    "question answering",
    "document retrieval",
    "hybrid search",
    "dense retrieval"
]


def fetch_arxiv_papers(search_query, max_results=300):
    encoded_query = quote_plus(search_query)

    base_url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=all:{encoded_query}"
        f"&start=0&max_results={max_results}"
    )

    feed = feedparser.parse(base_url)

    papers = []

    for entry in feed.entries:
        title = entry.title.replace("\n", " ").strip()
        abstract = entry.summary.replace("\n", " ").strip()

        authors = ", ".join(
            author.name
            for author in entry.authors
        )

        published = entry.published
        url = entry.link

        category = (
            entry.tags[0]["term"]
            if hasattr(entry, "tags")
            else "Unknown"
        )

        papers.append(
            {
                "title": title,
                "content": abstract,
                "authors": authors,
                "category": category,
                "published": published,
                "url": url,
                "source": "arXiv",
                "topic": search_query
            }
        )

    return papers


def build_arxiv_dataset():
    all_papers = []

    for topic in TOPICS:
        print(f"Fetching topic: {topic}")

        papers = fetch_arxiv_papers(
            search_query=topic,
            max_results=300
        )

        print(f"Fetched {len(papers)} papers.")

        all_papers.extend(papers)

        time.sleep(3)

    df = pd.DataFrame(all_papers)

    df = df.drop_duplicates(
        subset=["title", "content"]
    )

    df.to_csv(
        "data/arxiv_papers.csv",
        index=False
    )

    print("\nSaved arXiv dataset.")
    print(f"Total unique papers: {len(df)}")


if __name__ == "__main__":
    build_arxiv_dataset()