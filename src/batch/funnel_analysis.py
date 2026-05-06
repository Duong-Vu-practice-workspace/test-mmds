import json
from pathlib import Path
from typing import Dict, List
import pandas as pd


class FunnelAnalysis:
    """Analyze conversion funnel: Click → Cart → Order."""

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

    def calculate_funnel(self) -> Dict:
        """
        Calculate funnel metrics.

        Returns:
            Dictionary with funnel step counts and conversion rates
        """
        total_sessions = len(self.sessions)
        sessions_with_clicks = 0
        sessions_with_carts = 0
        sessions_with_orders = 0

        for session in self.sessions:
            events = session.get("events", [])
            event_types = [e["type"] for e in events]

            if "clicks" in event_types:
                sessions_with_clicks += 1
            if "carts" in event_types:
                sessions_with_carts += 1
            if "orders" in event_types:
                sessions_with_orders += 1

        return {
            "total_sessions": total_sessions,
            "sessions_with_clicks": sessions_with_clicks,
            "sessions_with_carts": sessions_with_carts,
            "sessions_with_orders": sessions_with_orders,
            "click_to_cart_rate": sessions_with_carts / sessions_with_clicks if sessions_with_clicks > 0 else 0,
            "cart_to_order_rate": sessions_with_orders / sessions_with_carts if sessions_with_carts > 0 else 0,
            "overall_conversion": sessions_with_orders / total_sessions if total_sessions > 0 else 0,
        }

    def session_complexity(self) -> Dict[str, int]:
        """
        Classify sessions by complexity.

        Returns:
            Dictionary with counts for each session type
        """
        categories = {
            "browse_only": 0,
            "cart_abandoner": 0,
            "buyer": 0,
        }

        for session in self.sessions:
            events = session.get("events", [])
            has_clicks = any(e["type"] == "clicks" for e in events)
            has_carts = any(e["type"] == "carts" for e in events)
            has_orders = any(e["type"] == "orders" for e in events)

            if has_orders:
                categories["buyer"] += 1
            elif has_carts and not has_orders:
                categories["cart_abandoner"] += 1
            elif has_clicks:
                categories["browse_only"] += 1

        return categories

    def save_funnel_report(self, output_path: str = "datasets/eda/funnel_report.json"):
        """Save funnel analysis results."""
        funnel = self.calculate_funnel()
        complexity = self.session_complexity()

        report = {
            "funnel": funnel,
            "session_complexity": complexity,
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report


if __name__ == "__main__":
    analysis = FunnelAnalysis()
    analysis.load_data(max_sessions=5000)

    funnel = analysis.calculate_funnel()
    print("Funnel Analysis:")
    for k, v in funnel.items():
        print(f"  {k}: {v}")

    complexity = analysis.session_complexity()
    print("\nSession Complexity:")
    for k, v in complexity.items():
        print(f"  {k}: {v}")
