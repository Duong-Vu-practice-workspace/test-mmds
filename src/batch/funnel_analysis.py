import json
import sys
from pathlib import Path
from typing import Dict, List
import pandas as pd

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.api.db import Database

class FunnelAnalysis:
    """Analyze conversion funnel: Click → Cart → Order."""

    def __init__(self, data_path: str = None, db: Database = None):
        if data_path is None:
            # Default to a relative path within the project
            data_path = Path(root_dir) / "datasets" / "otto-recommender-system" / "test.jsonl"
        
        self.data_path = Path(data_path)
        self.sessions = []
        self.db = db

    def load_data(self, max_sessions: int = 10000):
        """Load sessions from JSONL file."""
        self.sessions = []
        if not self.data_path.exists():
            print(f"Warning: Data path {self.data_path} does not exist.")
            return
            
        with open(self.data_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= max_sessions:
                    break
                self.sessions.append(json.loads(line.strip()))

    def calculate_funnel(self) -> Dict:
        """
        Calculate funnel metrics.
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
            "click_to_order_rate": sessions_with_orders / sessions_with_clicks if sessions_with_clicks > 0 else 0,
        }

    def session_complexity(self) -> List[Dict]:
        """
        Classify sessions by complexity and calculate averages.
        """
        stats = {
            "browse_only": {"count": 0, "total_len": 0},
            "cart_abandoner": {"count": 0, "total_len": 0},
            "buyer": {"count": 0, "total_len": 0},
        }

        for session in self.sessions:
            events = session.get("events", [])
            length = len(events)
            has_carts = any(e["type"] == "carts" for e in events)
            has_orders = any(e["type"] == "orders" for e in events)

            if has_orders:
                cat = "buyer"
            elif has_carts:
                cat = "cart_abandoner"
            else:
                cat = "browse_only"
            
            stats[cat]["count"] += 1
            stats[cat]["total_len"] += length

        total_sessions = len(self.sessions)
        results = []
        for cat, data in stats.items():
            if total_sessions > 0:
                results.append({
                    "session_type": cat,
                    "count": data["count"],
                    "avg_length": data["total_len"] / data["count"] if data["count"] > 0 else 0,
                    "pct_of_total": (data["count"] / total_sessions) * 100
                })
        
        return results

    def save_to_db(self):
        """Save analysis results to PostgreSQL."""
        if not self.db:
            print("Error: Database connection not provided.")
            return

        funnel = self.calculate_funnel()
        complexity = self.session_complexity()

        try:
            with self.db.cursor() as cur:
                # 1. Insert into funnel_stats
                cur.execute("""
                    INSERT INTO funnel_stats 
                        (total_sessions, sessions_with_clicks, sessions_with_carts, sessions_with_orders, 
                         click_to_cart_rate, cart_to_order_rate, click_to_order_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    funnel["total_sessions"], funnel["sessions_with_clicks"], 
                    funnel["sessions_with_carts"], funnel["sessions_with_orders"],
                    funnel["click_to_cart_rate"], funnel["cart_to_order_rate"], 
                    funnel["click_to_order_rate"]
                ))

                # 2. Update stats_sessions
                for item in complexity:
                    cur.execute("""
                        INSERT INTO stats_sessions (session_type, count, avg_length, pct_of_total)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_type) DO UPDATE SET
                            count = EXCLUDED.count,
                            avg_length = EXCLUDED.avg_length,
                            pct_of_total = EXCLUDED.pct_of_total
                    """, (item["session_type"], item["count"], item["avg_length"], item["pct_of_total"]))
                
                print("Successfully saved funnel analysis to database.")
        except Exception as e:
            print(f"Failed to save to database: {e}")

if __name__ == "__main__":
    # Initialize DB
    db = Database(host="localhost", port=5432, dbname="otto_recommender", user="otto", password="otto123")
    
    # Path to small dataset for testing
    data_path = Path(root_dir) / "datasets" / "test.jsonl" # Try local dataset first
    if not data_path.exists():
         # Fallback to absolute path provided by user if needed
         data_path = "/home/duongvct/Documents/workspace/PTIT/Y4T2/mining-on-massive-datasets-ptit-project/datasets/otto-recommender-system/test.jsonl"

    analysis = FunnelAnalysis(data_path=data_path, db=db)
    analysis.load_data(max_sessions=10000)

    if not analysis.sessions:
        print("No sessions loaded. Please check data path.")
    else:
        analysis.save_to_db()
        
        # Print summary
        funnel = analysis.calculate_funnel()
        print("\nFunnel Summary:")
        print(f"  Sessions: {funnel['total_sessions']}")
        print(f"  Conversion: {funnel['click_to_order_rate']*100:.2f}%")
