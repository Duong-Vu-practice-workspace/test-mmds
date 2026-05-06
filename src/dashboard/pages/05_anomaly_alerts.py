import streamlit as st
import pandas as pd
import psycopg2
import redis
from datetime import datetime


st.set_page_config(page_title="Anomaly Alerts", layout="wide")
st.title("🚨 Anomaly Alerts")

@st.cache_resource
def get_pg_conn():
    return psycopg2.connect("host=postgres dbname=otto_recommender user=otto password=otto123")

@st.cache_resource
def get_redis():
    return redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

pg = get_pg_conn()
r = get_redis()

st.markdown("### Active Alerts from PostgreSQL")

try:
    with pg.cursor() as cur:
        cur.execute("""
            SELECT alert_type, session, severity, alert_timestamp, details
            FROM anomaly_alerts
            ORDER BY alert_timestamp DESC
            LIMIT 50
        """)
        alerts = cur.fetchall()

    if alerts:
        df = pd.DataFrame(alerts, columns=["Type", "Session", "Severity", "Timestamp", "Details"])
        st.dataframe(df)

        severity_filter = st.selectbox("Filter by Severity", ["All", "high", "medium", "low"])
        if severity_filter != "All":
            filtered = df[df["Severity"] == severity_filter]
            st.dataframe(filtered)
    else:
        st.info("No alerts in PostgreSQL yet. Run the stream processor to generate alerts.")

except Exception as e:
    st.warning(f"PostgreSQL connection issue: {e}")
    st.info("Simulating alerts for demo...")

    alerts = [
        {"type": "bot_detection", "session": "sim_1234567", "severity": "high", "timestamp": str(datetime.now()), "details": "150 events/minute"},
        {"type": "traffic_spike", "session": "N/A", "severity": "high", "timestamp": str(datetime.now()), "details": "Events: 500/min (threshold: 300)"},
    ]

    for alert in alerts:
        color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert["severity"], "⚪")
        with st.expander(f"{color} {alert['type']} - Session: {alert['session']}"):
            st.markdown(f"**Severity**: {alert['severity']}")
            st.markdown(f"**Timestamp**: {alert['timestamp']}")
            st.markdown(f"**Details**: {alert['details']}")

st.markdown("---")
st.markdown("### Anomaly Statistics from DB")

try:
    with pg.cursor() as cur:
        cur.execute("""
            SELECT alert_type, COUNT(*) as count
            FROM anomaly_alerts
            GROUP BY alert_type
        """)
        stats = cur.fetchall()

    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bot_count = sum(c for t, c in stats if "bot" in t)
            st.metric("Bot Detections", bot_count)
        with col2:
            spike_count = sum(c for t, c in stats if "spike" in t)
            st.metric("Traffic Spikes", spike_count)
        with col3:
            fraud_count = sum(c for t, c in stats if "fraud" in t)
            st.metric("Click Fraud", fraud_count)
        with col4:
            cart_count = sum(c for t, c in stats if "cart" in t)
            st.metric("Cart Anomalies", cart_count)
    else:
        st.info("No anomaly statistics available yet")
except:
    st.warning("Could not load anomaly statistics")

st.markdown("---")
st.markdown("### Anomaly Rules Configuration")

st.markdown("#### Bot Detection")
bot_threshold = st.slider("Events per minute threshold", 50, 500, 100)
st.markdown(f"Current: {bot_threshold} events/minute")

st.markdown("#### Cart Behavior")
cart_threshold = st.slider("Max cart items", 20, 200, 50)
st.markdown(f"Current: {cart_threshold} items")

st.markdown("#### Traffic Spike")
sigma_threshold = st.slider("Sigma threshold (3-sigma rule)", 1.0, 5.0, 3.0, 0.5)
st.markdown(f"Current: {sigma_threshold} sigma")

st.markdown("---")
st.markdown("### Redis Connection for Real-time Alerts")

if st.button("Test Redis Connection"):
    try:
        r.ping()
        st.success("✅ Redis connected")
    except Exception as e:
        st.error(f"❌ Redis connection failed: {e}")

if st.button("Test PostgreSQL Connection"):
    try:
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM anomaly_alerts")
            count = cur.fetchone()[0]
        st.success(f"✅ PostgreSQL connected - {count} alerts in DB")
    except Exception as e:
        st.error(f"❌ PostgreSQL connection failed: {e}")
