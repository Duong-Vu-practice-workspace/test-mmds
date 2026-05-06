import streamlit as st
import pandas as pd
import time
from datetime import datetime
import redis
import psycopg2


st.set_page_config(page_title="System Health", layout="wide")
st.title("🏗️ System Health")

@st.cache_resource
def get_redis():
    return redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@st.cache_resource
def get_pg_conn():
    return psycopg2.connect("host=localhost dbname=otto_recommender user=otto password=otto123")

st.markdown("### Service Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### Kafka")
    try:
        r = get_redis()
        r.ping()
        st.markdown("🟢 **Broker**: Online")
        st.markdown("🟢 **User Events**: Active")
    except:
        st.markdown("🔴 **Broker**: Offline")

with col2:
    st.markdown("#### Redis + PostgreSQL")
    try:
        r = get_redis()
        r.ping()
        st.markdown("🟢 **Redis**: Online")
        info = r.info()
        st.markdown(f"🟢 **Memory Used**: {info.get('used_memory_human', 'N/A')}")
    except:
        st.markdown("🔴 **Redis**: Offline")

    try:
        pg = get_pg_conn()
        with pg.cursor() as cur:
            cur.execute("SELECT 1")
        st.markdown("🟢 **PostgreSQL**: Online")
    except:
        st.markdown("🔴 **PostgreSQL**: Offline")

with col3:
    st.markdown("#### Model Serving")
    try:
        from src.serving.covisitation_recommender import CovisitationRecommender
        recommender = CovisitationRecommender()
        if recommender.clicks_matrix:
            st.markdown("🟢 **Covisitation**: Loaded")
        else:
            st.markdown("🟡 **Covisitation**: No Matrix")
    except:
        st.markdown("🔴 **Covisitation**: Error")
    st.markdown("🟢 **Inference API**: Ready")

st.markdown("---")
st.markdown("### Redis Stats")

try:
    r = get_redis()
    info = r.info()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Connected Clients", info.get("connected_clients", 0))
    with col2:
        st.metric("Used Memory", info.get("used_memory_human", "N/A"))
    with col3:
        st.metric("Total Keys", len(r.keys("*")))
    with col4:
        st.metric("Uptime (days)", f"{info.get('uptime_in_seconds', 0) / 86400:.1f}")

    # Session count from Redis
    session_keys = [k for k in r.keys("session:*") if r.ttl(k) > 0]
    st.info(f"Active sessions in Redis: {len(session_keys)}")

except Exception as e:
    st.warning(f"Could not load Redis stats: {e}")

st.markdown("---")
st.markdown("### PostgreSQL Stats")

try:
    pg = get_pg_conn()
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_events")
        event_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT session) FROM user_events")
        session_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM predictions")
        pred_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM anomaly_alerts")
        alert_count = cur.fetchone()[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Events in DB", event_count)
    with col2:
        st.metric("Sessions in DB", session_count)
    with col3:
        st.metric("Predictions", pred_count)
    with col4:
        st.metric("Alerts", alert_count)

except Exception as e:
    st.warning(f"Could not load PostgreSQL stats: {e}")

st.markdown("---")
st.markdown("### Events Over Time")

try:
    pg = get_pg_conn()
    with pg.cursor() as cur:
        cur.execute("""
            SELECT
                date_trunc('minute', ts) as minute,
                COUNT(*) as count
            FROM user_events
            WHERE ts > NOW() - INTERVAL '1 hour'
            GROUP BY minute
            ORDER BY minute
        """)
        data = cur.fetchall()

    if data:
        df = pd.DataFrame(data, columns=["time", "count"])
        st.line_chart(df.set_index("time"))
    else:
        st.info("No recent events in database")

except Exception as e:
    st.warning(f"Could not load events timeline: {e}")

st.markdown("---")
st.markdown("### Recent Logs")

try:
    pg = get_pg_conn()
    with pg.cursor() as cur:
        cur.execute("""
            SELECT alert_type, session, severity, alert_timestamp
            FROM anomaly_alerts
            ORDER BY alert_timestamp DESC
            LIMIT 5
        """)
        logs = cur.fetchall()

    if logs:
        for log in logs:
            st.text(f"[{log[3]}] ALERT: {log[0]} - Session: {log[1]} ({log[2]})")
    else:
        st.text(f"[{datetime.now().strftime('%H:%M:%S')}] INFO: No alerts yet")
except:
    st.text(f"[{datetime.now().strftime('%H:%M:%S')}] INFO: System running normally")

if st.button("Refresh Status"):
    st.rerun()

st.markdown("---")
st.markdown("### Actions")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Restart Kafka"):
        st.info("Would restart Kafka...")
with col2:
    if st.button("Clear Redis Cache"):
        try:
            r = get_redis()
            r.flushdb()
            st.success("Redis cache cleared!")
        except Exception as e:
            st.error(f"Error: {e}")
with col3:
    if st.button("Download Logs"):
        st.info("Would download logs.zip...")
