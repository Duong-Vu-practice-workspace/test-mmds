import json
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
import logging
import redis
import psycopg2
from psycopg2.extras import Json

from src.streaming.anomaly_detector import AnomalyDetector
from src.serving.covisitation_recommender import CovisitationRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamProcessor:
    """Stream processor with Redis (real-time state) and PostgreSQL (persistent storage)."""

    def __init__(
        self,
        bootstrap_servers: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        pg_host: str = "localhost",
        pg_port: int = 5433,
        pg_db: str = "otto_recommender",
        pg_user: str = "otto",
        pg_password: str = "otto123",
        input_topic: str = "user-events",
        output_topic: str = "processed-events",
        predictions_topic: str = "predictions",
        alerts_topic: str = "anomaly-alerts",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.predictions_topic = predictions_topic
        self.alerts_topic = alerts_topic

        self.consumer = None
        self.producer = None
        self.anomaly_detector = AnomalyDetector()
        self.recommender = CovisitationRecommender()
        self.session_buffer = defaultdict(list)

        # Redis for real-time state
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

        # PostgreSQL for persistent storage
        self.pg_conn = psycopg2.connect(
            host=pg_host, port=pg_port, database=pg_db, user=pg_user, password=pg_password
        )
        self.pg_conn.autocommit = True
        self._init_pg_tables()

    def _init_pg_tables(self):
        """Initialize PostgreSQL tables if not exists."""
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id SERIAL PRIMARY KEY,
                    session TEXT NOT NULL,
                    aid INT NOT NULL,
                    ts TIMESTAMPTZ NOT NULL,
                    type TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_session ON user_events(session)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ts ON user_events(ts)")

    async def start(self):
        """Start Kafka consumer and producer."""
        self.consumer = AIOKafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id="stream-processor-group",
            auto_offset_reset="latest",
        )
        await self.consumer.start()

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.producer.start()
        logger.info("Stream processor started with Redis + PostgreSQL")

    async def stop(self):
        """Stop all connections."""
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.redis:
            self.redis.close()
        if self.pg_conn:
            self.pg_conn.close()
        logger.info("Stream processor stopped")

    async def run(self):
        """Main processing loop."""
        try:
            async for msg in self.consumer:
                await self._process_event(msg.value)
        except Exception as e:
            logger.error(f"Error in stream processor: {e}")

    async def _process_event(self, event: Dict[str, Any]):
        """Process a single event."""
        session_id = event.get("session")
        aid = event.get("aid")
        timestamp = event.get("ts")
        event_type = event.get("type")

        if not all([session_id, aid, timestamp, event_type]):
            return

        # Store in Redis (real-time state)
        self.redis.hset(f"session:{session_id}", mapping={
            "last_aid": aid,
            "last_ts": timestamp,
            "last_type": event_type,
        })
        self.redis.expire(f"session:{session_id}", 3600)
        self.redis.incr("global:events_total")

        # Store in PostgreSQL (persistent)
        with self.pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_events (session, aid, ts, type) VALUES (%s, %s, to_timestamp(%s/1000.0), %s)",
                (session_id, aid, timestamp, event_type)
            )

        # Update session buffer
        self.session_buffer[session_id].append({
            "aid": aid,
            "ts": timestamp,
            "type": event_type,
        })

        # Anomaly detection
        anomalies = self.anomaly_detector.check_event(session_id, aid, timestamp, event_type)
        if anomalies:
            for anomaly in anomalies:
                await self.producer.send(self.alerts_topic, anomaly)
                self._store_alert(anomaly)
                logger.warning(f"Anomaly: {anomaly['type']} in {session_id}")

        # Extract features
        features = self._extract_features(session_id)

        # Send processed event
        processed_event = {
            "session": session_id,
            "aid": aid,
            "ts": timestamp,
            "type": event_type,
            "features": features,
        }
        await self.producer.send(self.output_topic, processed_event)

        # Generate predictions if enough history
        if len(self.session_buffer[session_id]) >= 3:
            session_items = [e["aid"] for e in self.session_buffer[session_id]]
            predictions = self.recommender.recommend_multi_objective(session_items, top_k=20)

            prediction_msg = {
                "session": session_id,
                "predictions": predictions,
                "ts": timestamp,
                "input_items": session_items[-5:],
            }
            await self.producer.send(self.predictions_topic, prediction_msg)

            # Cache prediction in Redis
            self.redis.setex(
                f"prediction:{session_id}",
                300,
                json.dumps(predictions)
            )

            # Store in PostgreSQL
            self._store_prediction(session_id, timestamp, predictions, session_items[-5:])

        self._cleanup_old_sessions(timestamp)

    def _extract_features(self, session_id: str) -> Dict[str, Any]:
        """Extract real-time features for a session."""
        events = self.session_buffer[session_id]
        if not events:
            return {}

        return {
            "session_length": len(events),
            "click_count": sum(1 for e in events if e["type"] == "clicks"),
            "cart_count": sum(1 for e in events if e["type"] == "carts"),
            "order_count": sum(1 for e in events if e["type"] == "orders"),
            "duration_ms": events[-1]["ts"] - events[0]["ts"] if len(events) > 1 else 0,
            "unique_items": len(set(e["aid"] for e in events)),
        }

    def _store_alert(self, alert: Dict[str, Any]):
        """Store anomaly alert in PostgreSQL."""
        with self.pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO anomaly_alerts (session, alert_type, severity, alert_timestamp, details) VALUES (%s, %s, %s, to_timestamp(%s/1000.0), %s)",
                (alert.get("session"), alert["type"], alert.get("severity"), alert.get("timestamp"), json.dumps(alert))
            )

    def _store_prediction(self, session_id: str, timestamp: int, predictions: Dict, input_items: List[int]):
        """Store prediction in PostgreSQL."""
        with self.pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO predictions (session, ts, predicted_items, input_items, model_type) VALUES (%s, to_timestamp(%s/1000.0), %s, %s, %s)",
                (session_id, timestamp, predictions.get("clicks", []), input_items, "covisitation")
            )

    def _cleanup_old_sessions(self, current_ts: int, max_age_ms: int = 3600000):
        """Clean up old sessions from memory."""
        old_sessions = [
            sid for sid in self.session_buffer
            if self.session_buffer[sid] and
            current_ts - self.session_buffer[sid][-1]["ts"] > max_age_ms
        ]
        for sid in old_sessions:
            del self.session_buffer[sid]
        self.anomaly_detector.cleanup_old_sessions(current_ts, max_age_ms)


async def main():
    import argparse
    from src.core.config import get_config

    parser = argparse.ArgumentParser(description="OTTO Stream Processor with Redis + PostgreSQL")
    parser.add_argument("--bootstrap-servers", type=str, help="Kafka bootstrap servers")
    args = parser.parse_args()

    config = get_config()
    bootstrap_servers = args.bootstrap_servers or config.get("kafka", {}).get("bootstrap_servers", "localhost:29092")

    processor = StreamProcessor(bootstrap_servers)

    try:
        await processor.start()
        logger.info("Stream processor running. Press Ctrl+C to stop.")
        await processor.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        await processor.stop()


if __name__ == "__main__":
    asyncio.run(main())
