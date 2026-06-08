import pandas as pd
from sklearn.decomposition import PCA


def create_embedding_map(embeddings, dataframe):
    if hasattr(embeddings, "cpu"):
        embeddings_array = embeddings.cpu().numpy()
    else:
        embeddings_array = embeddings

    pca = PCA(n_components=2)
    reduced_embeddings = pca.fit_transform(embeddings_array)

    visualization_df = pd.DataFrame({
        "x": reduced_embeddings[:, 0],
        "y": reduced_embeddings[:, 1],
        "title": dataframe["title"],
        "category": dataframe["category"]
    })

    return visualization_df