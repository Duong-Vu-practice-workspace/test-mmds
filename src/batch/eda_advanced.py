import json
from pathlib import Path
from typing import Dict, List
import pandas as pd
import matplotlib.pyplot as plt


class BatchEDA:
    """Lightweight EDA using Pandas (no Spark needed)."""

    def __init__(self, data_path: str = "datasets/raw/train.jsonl"):
        self.data_path = Path(data_path)
        self.df = None
        self.sessions = []

    def load_data(self, max_sessions: int = 10000):
        """Load sessions from JSONL file (with limit for memory)."""
        self.sessions = []
        with open(self.data_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= max_sessions:
                    break
                self.sessions.append(json.loads(line.strip()))

        rows = []
        for session in self.sessions:
            session_id = session["session"]
            for event in session.get("events", []):
                rows.append({
                    "session": session_id,
                    "aid": event["aid"],
                    "ts": event["ts"],
                    "type": event["type"],
                })

        self.df = pd.DataFrame(rows)
        return self.df

    def event_distribution(self) -> Dict:
        """Calculate event type distribution."""
        if self.df is None:
            self.load_data()

        return self.df["type"].value_counts().to_dict()

    def session_length_distribution(self) -> pd.DataFrame:
        """Get session length statistics."""
        if self.df is None:
            self.load_data()

        session_lengths = self.df.groupby("session").size()
        return pd.DataFrame({
            "length": session_lengths.values,
        })

    def temporal_patterns(self) -> pd.DataFrame:
        """Analyze events by hour and day."""
        if self.df is None:
            self.load_data()

        self.df["hour"] = pd.to_datetime(self.df["ts"], unit='ms').dt.hour
        self.df["day_of_week"] = pd.to_datetime(self.df["ts"], unit='ms').dt.dayofweek

        hourly = self.df.groupby("hour").size().reset_index(name='count')
        daily = self.df.groupby("day_of_week").size().reset_index(name='count')

        return {"hourly": hourly, "daily": daily}

    def item_popularity(self, top_n: int = 20) -> pd.DataFrame:
        """Get most popular items."""
        if self.df is None:
            self.load_data()

        return self.df["aid"].value_counts().head(top_n).reset_index()

    def save_eda_report(self, output_path: str = "datasets/eda/eda_report.json"):
        """Save EDA results to file."""
        results = {
            "event_distribution": self.event_distribution(),
            "total_sessions": len(self.sessions),
            "total_events": len(self.df) if self.df is not None else 0,
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        return results


if __name__ == "__main__":
    eda = BatchEDA()
    eda.load_data(max_sessions=5000)

    print("Event Distribution:", eda.event_distribution())
    print("Session Length Stats:", eda.session_length_distribution().describe())

    temporal = eda.temporal_patterns()
    print("\nHourly Pattern:", temporal["hourly"].head())
