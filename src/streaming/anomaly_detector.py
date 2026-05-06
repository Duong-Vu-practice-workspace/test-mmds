from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class AnomalyDetector:
    """Rule-based anomaly detection for real-time event streams."""

    def __init__(self):
        self.session_events = defaultdict(list)
        self.session_start_times = {}
        self.global_stats = {
            "events_per_minute": [],
            "sessions_per_minute": set(),
            "baseline_events_per_min": None,
        }
        self.minute_buckets = {}

    def check_event(
        self,
        session_id: str,
        aid: int,
        timestamp: int,
        event_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check a single event for anomalies.

        Returns:
            Anomaly dict if detected, None otherwise
        """
        anomalies = []

        self._update_session_state(session_id, aid, timestamp, event_type)

        bot_result = self._check_bot_behavior(session_id, timestamp)
        if bot_result:
            anomalies.append(bot_result)

        cart_result = self._check_unusual_cart_behavior(session_id)
        if cart_result:
            anomalies.append(cart_result)

        click_fraud_result = self._check_click_fraud(session_id, aid)
        if click_fraud_result:
            anomalies.append(click_fraud_result)

        duration_result = self._check_outlier_session_duration(session_id, timestamp)
        if duration_result:
            anomalies.append(duration_result)

        traffic_result = self._check_traffic_spike(timestamp)
        if traffic_result:
            anomalies.append(traffic_result)

        return anomalies if anomalies else None

    def _update_session_state(self, session_id: str, aid: int, timestamp: int, event_type: str):
        """Update internal state for a session."""
        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = timestamp

        self.session_events[session_id].append({
            "aid": aid,
            "ts": timestamp,
            "type": event_type,
        })

        minute_bucket = timestamp // (60 * 1000)
        self.minute_buckets[minute_bucket] = self.minute_buckets.get(minute_bucket, 0) + 1

        if self.global_stats["baseline_events_per_min"] is None and len(self.minute_buckets) > 10:
            values = list(self.minute_buckets.values())
            self.global_stats["baseline_events_per_min"] = sum(values) / len(values)

    def _check_bot_behavior(self, session_id: str, current_ts: int) -> Optional[Dict]:
        """Detect sessions with too many clicks in a short time."""
        events = self.session_events[session_id]
        recent_events = [
            e for e in events
            if current_ts - e["ts"] < 60000
        ]

        if len(recent_events) > 100:
            return {
                "type": "bot_detection",
                "session": session_id,
                "events_in_last_minute": len(recent_events),
                "threshold": 100,
                "severity": "high",
                "timestamp": current_ts,
            }
        return None

    def _check_unusual_cart_behavior(self, session_id: str) -> Optional[Dict]:
        """Detect sessions with too many items in cart."""
        events = self.session_events[session_id]
        cart_items = [e for e in events if e["type"] == "carts"]

        if len(cart_items) > 50:
            return {
                "type": "unusual_cart_behavior",
                "session": session_id,
                "cart_items_count": len(cart_items),
                "threshold": 50,
                "severity": "medium",
                "timestamp": events[-1]["ts"] if events else 0,
            }
        return None

    def _check_click_fraud(self, session_id: str, current_aid: int) -> Optional[Dict]:
        """Detect repeated clicks on the same item."""
        events = self.session_events[session_id]
        recent_clicks = [
            e for e in events[-20:]
            if e["type"] == "clicks" and e["aid"] == current_aid
        ]

        if len(recent_clicks) >= 5:
            return {
                "type": "click_fraud",
                "session": session_id,
                "aid": current_aid,
                "repeat_count": len(recent_clicks),
                "threshold": 5,
                "severity": "medium",
                "timestamp": events[-1]["ts"] if events else 0,
            }
        return None

    def _check_outlier_session_duration(self, session_id: str, current_ts: int) -> Optional[Dict]:
        """Detect sessions with unusual duration."""
        if session_id not in self.session_start_times:
            return None

        start_ts = self.session_start_times[session_id]
        duration_seconds = (current_ts - start_ts) / 1000

        if duration_seconds > 24 * 3600:
            return {
                "type": "outlier_duration_long",
                "session": session_id,
                "duration_hours": duration_seconds / 3600,
                "threshold_hours": 24,
                "severity": "low",
                "timestamp": current_ts,
            }

        if duration_seconds < 1 and len(self.session_events[session_id]) > 3:
            return {
                "type": "outlier_duration_short",
                "session": session_id,
                "duration_seconds": duration_seconds,
                "event_count": len(self.session_events[session_id]),
                "severity": "low",
                "timestamp": current_ts,
            }
        return None

    def _check_traffic_spike(self, timestamp: int) -> Optional[Dict]:
        """Detect traffic spikes using 3-sigma rule."""
        baseline = self.global_stats["baseline_events_per_min"]
        if baseline is None:
            return None

        minute_bucket = timestamp // (60 * 1000)
        current_rate = self.minute_buckets.get(minute_bucket, 0)

        if len(self.minute_buckets) < 10:
            return None

        values = list(self.minute_buckets.values())
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5

        if current_rate > mean + 3 * std:
            return {
                "type": "traffic_spike",
                "current_rate": current_rate,
                "mean_rate": mean,
                "std": std,
                "threshold": mean + 3 * std,
                "severity": "high",
                "timestamp": timestamp,
            }
        return None

    def get_session_summary(self, session_id: str) -> Dict:
        """Get summary of session for analysis."""
        if session_id not in self.session_events:
            return {}

        events = self.session_events[session_id]
        return {
            "session": session_id,
            "event_count": len(events),
            "duration_seconds": (
                (events[-1]["ts"] - self.session_start_times[session_id]) / 1000
                if events else 0
            ),
            "event_types": {
                "clicks": sum(1 for e in events if e["type"] == "clicks"),
                "carts": sum(1 for e in events if e["type"] == "carts"),
                "orders": sum(1 for e in events if e["type"] == "orders"),
            },
        }

    def cleanup_old_sessions(self, current_ts: int, max_age_ms: int = 3600000):
        """Clean up sessions older than max_age_ms."""
        old_sessions = [
            sid for sid in self.session_start_times
            if current_ts - self.session_start_times[sid] > max_age_ms
        ]
        for sid in old_sessions:
            del self.session_events[sid]
            del self.session_start_times[sid]
