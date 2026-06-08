import plotly.express as px


def create_interactive_embedding_plot(embedding_map_df):
    fig = px.scatter(
        embedding_map_df,
        x="x",
        y="y",
        color="category",
        hover_name="title",
        hover_data=["category"],
        title="Interactive Embedding Map"
    )

    fig.update_layout(
        height=550,
        legend_title_text="Category"
    )

    return fig