import pandas as pd


ARXIV_DATA_PATH = "data/arxiv_papers.csv"
OUTPUT_PATH = "data/research_corpus.csv"


def build_research_corpus():
    arxiv_df = pd.read_csv(ARXIV_DATA_PATH)

    required_columns = [
        "title",
        "content",
        "category",
        "authors",
        "published",
        "url",
        "source"
    ]

    arxiv_df = arxiv_df[required_columns]

    arxiv_df = arxiv_df.drop_duplicates(
        subset=["title", "content"]
    )

    arxiv_df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    return arxiv_df


if __name__ == "__main__":
    df = build_research_corpus()

    print(df.head())
    print("\nReal research corpus created successfully.")
    print(f"Total documents: {len(df)}")
    print(f"Saved to: {OUTPUT_PATH}")