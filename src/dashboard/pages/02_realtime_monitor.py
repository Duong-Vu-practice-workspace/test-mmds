import streamlit as st
import pandas as pd
import redis
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
import json


st.set_page_config(page_title="Real-time Monitor", layout="wide")
st.title("⚡ Real-time Monitor")

@st.cache_resource
def get_redis():
    return redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

@st.cache_resource
def get_pg_conn():
    return psycopg2.connect("host=postgres dbname=otto_recommender user=otto password=otto123")

st.markdown("### Live Event Stream")

# Get real-time stats from Redis
r = get_redis()
pg = get_pg_conn()

col1, col2, col3, col4 = st.columns(4)

with col1:
    try:
        events_total = int(r.get("global:events_total") or 0)
    except:
        events_total = 0
    st.metric("Events Total", events_total)

with col2:
    try:
        session_keys = r.keys("session:*")
        active_sessions = len([k for k in session_keys if r.ttl(k) > 0])
    except:
        active_sessions = 0
    st.metric("Active Sessions", active_sessions)

with col3:
    try:
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM user_events WHERE ts > NOW() - INTERVAL '1 minute'")
            events_per_min = cur.fetchone()[0]
    except:
        events_per_min = 0
    st.metric("Events/Min", events_per_min)

with col4:
    st.metric("Status", "🟢 Online")

st.markdown("---")
st.markdown("### Popular Items (Real-time from Redis)")

try:
    # Get recent session data from Redis
    session_keys = list(r.keys("session:*"))[:100]
    item_counts = {}
    for key in session_keys:
        data = r.hgetall(key)
        if "last_aid" in data:
            aid = int(data["last_aid"])
            item_counts[aid] = item_counts.get(aid, 0) + 1

    if item_counts:
        popular_items = pd.DataFrame([
            {"Item ID": aid, "Clicks": count}
            for aid, count in sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ])
        st.bar_chart(popular_items.set_index("Item ID"))
    else:
        st.info("No recent session data in Redis")
except Exception as e:
    st.warning(f"Redis connection issue: {e}")

st.markdown("---")
st.markdown("### Recent Events from PostgreSQL")

try:
    with pg.cursor() as cur:
        cur.execute("""
            SELECT session, aid, ts, type
            FROM user_events
            ORDER BY ts DESC
            LIMIT 10
        """)
        recent = cur.fetchall()
        if recent:
            df = pd.DataFrame(recent, columns=["Session", "Item ID", "Timestamp", "Type"])
            st.dataframe(df)
        else:
            st.info("No events in PostgreSQL yet")
except Exception as e:
    st.warning(f"PostgreSQL connection issue: {e}")

st.markdown("---")
st.markdown("### Session Activity Timeline (Last Hour)")

try:
    with pg.cursor() as cur:
        cur.execute("""
            SELECT
                date_trunc('minute', ts) as minute,
                COUNT(*) as event_count
            FROM user_events
            WHERE ts > NOW() - INTERVAL '1 hour'
            GROUP BY minute
            ORDER BY minute
        """)
        data = cur.fetchall()
        if data:
            timeline_df = pd.DataFrame(data, columns=["time", "count"])
            st.line_chart(timeline_df.set_index("time"))
        else:
            st.info("No data for timeline")
except Exception as e:
    st.warning(f"Could not load timeline: {e}")

st.markdown("---")
st.markdown("### Connection Settings")

redis_host = st.text_input("Redis Host", "redis")
pg_host = st.text_input("PostgreSQL Host", "postgres")

if st.button("Test Connections"):
    try:
        r_test = redis.Redis(host=redis_host, port=6379, db=0)
        r_test.ping()
        st.success("✅ Redis connected")
    except Exception as e:
        st.error(f"❌ Redis connection failed: {e}")

    try:
        pg_test = psycopg2.connect(f"host={pg_host} dbname=otto_recommender user=otto password=otto123")
        pg_test.close()
        st.success("✅ PostgreSQL connected")
    except Exception as e:
        st.error(f"❌ PostgreSQL connection failed: {e}")
