import json
from pathlib import Path
from typing import Dict, List
import pandas as pd
from collections import defaultdict


class UserSegmentation:
    """Lightweight user segmentation using Pandas."""

    def __init__(self, data_path: str = "datasets/raw/train.jsonl"):
        self.data_path = Path(data_path)
        self.sessions = []

    def load_data(self, max_sessions: int = 10000):
        """Load sessions from JSONL file."""
        self.sessions = []
        with open(self.data_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= max_sessions:
                    break
                self.sessions.append(json.loads(line.strip()))

    def extract_features(self) -> pd.DataFrame:
        """Extract features for each session."""
        features = []

        for session in self.sessions:
            events = session.get("events", [])
            if not events:
                continue

            session_data = {
                "session": session["session"],
                "session_length": len(events),
                "num_clicks": sum(1 for e in events if e["type"] == "clicks"),
                "num_carts": sum(1 for e in events if e["type"] == "carts"),
                "num_orders": sum(1 for e in events if e["type"] == "orders"),
                "unique_items": len(set(e["aid"] for e in events)),
            }

            total = session_data["session_length"]
            session_data["click_ratio"] = session_data["num_clicks"] / total if total > 0 else 0
            session_data["has_order"] = 1 if session_data["num_orders"] > 0 else 0

            features.append(session_data)

        return pd.DataFrame(features)

    def simple_segmentation(self) -> Dict[str, pd.DataFrame]:
        """
        Simple rule-based segmentation.

        Returns:
            Dictionary mapping segment name to DataFrame of sessions
        """
        df = self.extract_features()

        segments = {
            "heavy_browser": df[df["session_length"] > 10],
            "quick_buyer": df[(df["session_length"] <= 5) & (df["has_order"] == 1)],
            "window_shopper": df[(df["session_length"] > 5) & (df["has_order"] == 0) & (df["num_clicks"] > 5)],
            "cart_abandoner": df[(df["num_carts"] > 0) & (df["num_orders"] == 0)],
        }

        return segments

    def get_segment_stats(self) -> pd.DataFrame:
        """Get statistics per segment."""
        segments = self.simple_segmentation()

        stats = []
        for name, df in segments.items():
            if len(df) > 0:
                stats.append({
                    "segment": name,
                    "count": len(df),
                    "avg_session_length": df["session_length"].mean(),
                    "avg_clicks": df["num_clicks"].mean(),
                    "conversion_rate": df["has_order"].mean(),
                })

        return pd.DataFrame(stats)


class ItemAffinityAnalysis:
    """Analyze item-to-item relationships."""

    def __init__(self, data_path: str = "datasets/raw/train.jsonl"):
        self.data_path = Path(data_path)
        self.item_pairs = defaultdict(int)

    def load_data(self, max_sessions: int = 10000):
        """Load and analyze item co-occurrences."""
        with open(self.data_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= max_sessions:
                    break

                session = json.loads(line.strip())
                events = session.get("events", [])
                items = [e["aid"] for e in events]

                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        pair = tuple(sorted([items[i], items[j]]))
                        self.item_pairs[pair] += 1

    def get_top_pairs(self, top_n: int = 20) -> pd.DataFrame:
        """Get top N item pairs by co-occurrence."""
        sorted_pairs = sorted(self.item_pairs.items(), key=lambda x: x[1], reverse=True)

        return pd.DataFrame([
            {"item1": pair[0], "item2": pair[1], "count": count}
            for pair, count in sorted_pairs[:top_n]
        ])

    def get_item_popularity(self, top_n: int = 20) -> pd.DataFrame:
        """Get most popular items."""
        item_counts = defaultdict(int)
        for (item1, item2), count in self.item_pairs.items():
            item_counts[item1] += count
            item_counts[item2] += count

        sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
        return pd.DataFrame([
            {"item_id": item, "cooccurrence_count": count}
            for item, count in sorted_items[:top_n]
        ])


if __name__ == "__main__":
    seg = UserSegmentation()
    seg.load_data(max_sessions=5000)

    print("Segment Statistics:")
    print(seg.get_segment_stats())

    print("\nItem Affinity Analysis:")
    affinity = ItemAffinityAnalysis()
    affinity.load_data(max_sessions=5000)

    print("\nTop Item Pairs:")
    print(affinity.get_top_pairs(10))
