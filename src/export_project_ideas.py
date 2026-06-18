import json
import os
from datetime import datetime
from typing import List, Dict


def export_project_ideas_to_json(
    project_ideas: List[Dict],
    query: str,
    output_dir: str = "outputs"
) -> str:
    """
    Exports generated project ideas to a JSON file.

    This makes the pipeline output reusable for:
    - Streamlit dashboard
    - FastAPI API response
    - README examples
    - project documentation
    - future frontend integration
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = create_safe_filename(query)

    filename = f"project_ideas_{safe_query}_{timestamp}.json"
    output_path = os.path.join(output_dir, filename)

    export_payload = {
        "query": query,
        "generated_at": datetime.now().isoformat(),
        "total_project_ideas": len(project_ideas),
        "project_ideas": project_ideas
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(export_payload, file, indent=4, ensure_ascii=False)

    return output_path


def create_safe_filename(text: str, max_length: int = 50) -> str:
    """
    Converts a query into a safe filename.

    Example:
    'RAG systems for question answering'
    becomes:
    'rag_systems_for_question_answering'
    """

    safe_text = text.lower().strip()
    safe_text = safe_text.replace(" ", "_")

    allowed_chars = []

    for char in safe_text:
        if char.isalnum() or char == "_":
            allowed_chars.append(char)

    safe_text = "".join(allowed_chars)

    if not safe_text:
        safe_text = "query"

    return safe_text[:max_length]