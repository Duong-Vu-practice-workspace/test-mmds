"""
Seed Popular Items — Pre-computes top items from JSONL and saves to PostgreSQL.
This provides the data for the 'Cold Start' strategy.
"""

import json
import logging
from collections import Counter
from pathlib import Path

from src.api.db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("seeder")


def seed_popular_items(file_path: str, top_k: int = 100):
    """
    Read JSONL, count occurrences of each aid per type, and save to Postgres.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return

    # Initialize counters
    counts = {
        "clicks": Counter(),
        "carts": Counter(),
        "orders": Counter()
    }

    logger.info(f"Phase 1: Reading {file_path} (this may take a minute)...")
    
    line_count = 0
    try:
        with open(path, "r") as f:
            for line in f:
                line_count += 1
                session_data = json.loads(line)
                for event in session_data.get("events", []):
                    etype = event["type"]
                    aid = event["aid"]
                    if etype in counts:
                        counts[etype][aid] += 1
                
                if line_count % 10000 == 0:
                    logger.info(f"  Processed {line_count} sessions...")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return

    logger.info("Phase 2: Connecting to PostgreSQL...")
    try:
        db = Database(
            host="localhost", 
            port=5432, 
            dbname="otto_recommender", 
            user="otto", 
            password="otto123"
        )
        
        with db.cursor() as cur:
            # Clear old data
            logger.info("  Clearing old popular_items data...")
            cur.execute("DELETE FROM popular_items WHERE time_scope = 'all_time'")
            
            # Insert new data
            for etype, counter in counts.items():
                logger.info(f"  Inserting top {top_k} for {etype}...")
                top_items = counter.most_common(top_k)
                
                for rank, (aid, count) in enumerate(top_items, 1):
                    cur.execute(
                        """
                        INSERT INTO popular_items (time_scope, event_type, aid, count, rank)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        ("all_time", etype, aid, count, rank)
                    )
        
        db.close()
        logger.info("✅ Done! Popular items seeded successfully.")
        
    except Exception as e:
        logger.error(f"Database error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed popular items from JSONL to PostgreSQL")
    parser.add_argument("--file", default="literature-review/duong/test.jsonl", help="Path to JSONL file")
    parser.add_argument("--top", type=int, default=100, help="Number of top items per category")
    args = parser.parse_args()

    seed_popular_items(args.file, args.top)
