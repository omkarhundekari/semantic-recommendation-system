from datetime import datetime
from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
QUERY_LOG_PATH = LOGS_DIR / "query_history.csv"
FEEDBACK_LOG_PATH = LOGS_DIR / "feedback.csv"


def log_query(query):
    LOGS_DIR.mkdir(exist_ok=True)

    new_entry = pd.DataFrame(
        [
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "query": query
            }
        ]
    )

    new_entry.to_csv(
        QUERY_LOG_PATH,
        mode="a",
        header=False,
        index=False
    )


def log_feedback(document_title, feedback):
    LOGS_DIR.mkdir(exist_ok=True)

    new_entry = pd.DataFrame(
        [
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "document_title": document_title,
                "feedback": feedback
            }
        ]
    )

    new_entry.to_csv(
        FEEDBACK_LOG_PATH,
        mode="a",
        header=False,
        index=False
    )