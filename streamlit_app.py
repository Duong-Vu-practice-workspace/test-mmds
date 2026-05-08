import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="OTTO Recommender Pipeline Dashboard",
    page_icon="🤖",
    layout="wide",
)

API_URL = "http://localhost:8000"

def get_stats():
    try:
        resp = requests.get(f"{API_URL}/api/stats")
        return resp.json()
    except:
        return None

def get_health():
    try:
        resp = requests.get(f"{API_URL}/api/health")
        return resp.json()
    except:
        return None


st.title("🤖 OTTO Recommender Pipeline")
st.markdown("---")

# --- Sidebar ---
st.sidebar.header("System Status")
health = get_health()
if health:
    st.sidebar.success(f"API: {health['status'].upper()}")
    st.sidebar.info(f"Redis: {health['redis']}")
    st.sidebar.info(f"Postgres: {health['postgres']}")
else:
    st.sidebar.error("API: OFFLINE")

st.sidebar.markdown("---")
st.sidebar.subheader("Settings")
refresh_rate = st.sidebar.slider("Auto-refresh (seconds)", 5, 60, 10)
if st.sidebar.button("Manual Refresh"):
    st.rerun()

# --- Main Stats ---
stats = get_stats()
if stats:
    # 1. Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Sessions", stats["active_sessions"])
    with col2:
        st.metric("Collected Events", stats["collected_events"])
    with col3:
        pred_stats = stats.get("prediction_stats", {})
        total_preds = pred_stats.get("total_predictions", 0)
        st.metric("Total Predictions", total_preds)
    with col4:
        avg_latency = pred_stats.get("avg_latency_ms") or 0
        st.metric("Avg Latency", f"{avg_latency:.1f} ms")

    st.markdown("---")

    # 2. Charts Section
    st.header("📊 Live Analytics")
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Event Type Distribution")
        ev_dist = stats.get("event_distribution", [])
        if ev_dist:
            df_ev = pd.DataFrame(ev_dist)
            fig_ev = px.bar(df_ev, x='event_type', y='count', 
                           color='event_type',
                           color_discrete_sequence=px.colors.qualitative.Pastel,
                           template="plotly_dark")
            fig_ev.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
            st.plotly_chart(fig_ev, use_container_width=True)
        else:
            st.info("No event data yet.")

    with row1_col2:
        st.subheader("Predictions by Model")
        usage = stats.get("model_usage", [])
        if usage:
            df_usage = pd.DataFrame(usage)
            fig_usage = px.pie(df_usage, values='count', names='model_used', 
                              hole=.4,
                              color_discrete_sequence=px.colors.qualitative.Bold,
                              template="plotly_dark")
            fig_usage.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
            st.plotly_chart(fig_usage, use_container_width=True)
        else:
            st.info("No prediction data yet.")

    # 3. Popular Items Section
    st.markdown("---")
    st.subheader("🔥 Top Popular Items (Pre-computed)")
    pop_type = st.radio("Item Type", ["clicks", "carts", "orders"], horizontal=True)
    
    try:
        pop_resp = requests.get(f"{API_URL}/api/popular/{pop_type}?limit=10")
        if pop_resp.status_code == 200:
            pop_items = pop_resp.json().get("items", [])
            if pop_items:
                df_pop = pd.DataFrame(pop_items)
                df_pop['aid'] = df_pop['aid'].astype(str) # treat as category for plotting
                fig_pop = px.bar(df_pop, x='aid', y='count', 
                               color='count',
                               labels={'aid': 'Article ID', 'count': 'Total Interactions'},
                               color_continuous_scale=px.colors.sequential.Viridis,
                               template="plotly_dark")
                fig_pop.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
                st.plotly_chart(fig_pop, use_container_width=True)
            else:
                st.info(f"No popular items found for {pop_type}.")
    except Exception as e:
        st.error(f"Error fetching popular items: {e}")

    st.markdown("---")

    # 4. Advanced Analytics Section
    st.header("🔬 Advanced Analytics")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Conversion Funnel", "⏰ Hourly Traffic", "👥 Session Insights", "⚡ Spark Performance"])
    
    with tab1:
        # ... (Funnel code stays same)
        st.subheader("User Conversion Funnel")
        funnel_data = stats.get("funnel_stats", {})
        if funnel_data:
            df_funnel = pd.DataFrame({
                "Stage": ["Total Sessions", "Sessions with Clicks", "Sessions with Carts", "Sessions with Orders"],
                "Count": [
                    funnel_data.get("total_sessions", 0),
                    funnel_data.get("sessions_with_clicks", 0),
                    funnel_data.get("sessions_with_carts", 0),
                    funnel_data.get("sessions_with_orders", 0)
                ]
            })
            fig_funnel = px.funnel(df_funnel, x='Count', y='Stage', 
                                  color_discrete_sequence=px.colors.qualitative.Prism,
                                  template="plotly_dark")
            st.plotly_chart(fig_funnel, use_container_width=True)
            
            # Additional Conversion Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Click -> Cart", f"{funnel_data.get('click_to_cart_rate', 0)*100:.1f}%")
            c2.metric("Cart -> Order", f"{funnel_data.get('cart_to_order_rate', 0)*100:.1f}%")
            c3.metric("Click -> Order", f"{funnel_data.get('click_to_order_rate', 0)*100:.1f}%")
        else:
            st.info("Funnel data not yet computed.")

    with tab2:
        st.subheader("Hourly Traffic Trends")
        hourly = stats.get("hourly_stats", [])
        if hourly:
            df_hourly = pd.DataFrame(hourly)
            df_hourly['window_start'] = pd.to_datetime(df_hourly['window_start'])
            fig_hourly = px.area(df_hourly, x='window_start', y=['total_clicks', 'total_carts', 'total_orders'],
                               labels={'value': 'Count', 'window_start': 'Time'},
                               color_discrete_sequence=px.colors.qualitative.Safe,
                               template="plotly_dark")
            fig_hourly.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_hourly, use_container_width=True)
        else:
            st.info("Hourly traffic data not available.")

    with tab3:
        st.subheader("Session Type Distribution")
        session_dist = stats.get("session_distribution", [])
        if session_dist:
            df_sess = pd.DataFrame(session_dist)
            fig_sess = px.bar(df_sess, x='session_type', y='count',
                             color='avg_length',
                             labels={'count': 'Number of Sessions', 'avg_length': 'Avg Events/Session'},
                             color_continuous_scale=px.colors.sequential.Tealgrn,
                             template="plotly_dark")
            st.plotly_chart(fig_sess, use_container_width=True)
        else:
            st.info("Session distribution data not available.")

    with tab4:
        st.subheader("Spark Streaming Performance")
        spark_metrics = stats.get("spark_metrics", [])
        if spark_metrics:
            df_spark = pd.DataFrame(spark_metrics)
            df_spark['timestamp'] = pd.to_datetime(df_spark['timestamp'])
            
            # Row 1: Rates
            st.markdown("**Processing vs Input Rate (rows/sec)**")
            fig_rates = px.line(df_spark, x='timestamp', y=['input_rows_per_second', 'processed_rows_per_second'],
                               color_discrete_sequence=['#ff4b4b', '#00d4ff'],
                               template="plotly_dark")
            fig_rates.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300)
            st.plotly_chart(fig_rates, use_container_width=True)
            
            # Row 2: Batch Duration
            st.markdown("**Batch Processing Duration (ms)**")
            fig_batch = px.bar(df_spark, x='timestamp', y='batch_duration_ms',
                              color='num_input_rows',
                              template="plotly_dark")
            fig_batch.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300)
            st.plotly_chart(fig_batch, use_container_width=True)
        else:
            st.info("Spark metrics not yet collected. Ensure Spark job is running.")

    # 5. Latency History
    st.subheader("Prediction Latency History")
    lat_hist = stats.get("latency_history", [])
    if lat_hist:
        df_lat = pd.DataFrame(lat_hist)
        df_lat['created_at'] = pd.to_datetime(df_lat['created_at'])
        fig_lat = px.line(df_lat, x='created_at', y='latency_ms', color='model_used',
                         labels={'latency_ms': 'Latency (ms)', 'created_at': 'Time'},
                         template="plotly_dark")
        fig_lat.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)
        st.plotly_chart(fig_lat, use_container_width=True)
    else:
        st.info("Insufficient latency data.")

    # 5. Recent Activity
    st.markdown("---")
    st.subheader("📋 Recent Predictions")
    recent = stats.get("recent_predictions", [])
    if recent:
        df_recent = pd.DataFrame(recent)
        # Reorder and rename columns for display
        cols = ['created_at', 'session_id', 'model_used', 'session_length', 'latency_ms']
        df_disp = df_recent[cols].copy()
        df_disp['created_at'] = pd.to_datetime(df_disp['created_at']).dt.strftime('%H:%M:%S')
        st.dataframe(df_disp, use_container_width=True)
    else:
        st.info("No recent activity.")

st.markdown("---")

# --- Quick Recommendation Demo ---
st.header("🎯 Live Recommendation Demo")

with st.expander("Try it out!", expanded=False):
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        session_id = st.number_input("Session ID", value=12345, step=1)
        aid = st.number_input("Add Article ID (aid)", value=1, step=1)
        etype = st.selectbox("Event Type", ["clicks", "carts", "orders"])
        
        if st.button("Send Event & Get Recommendations"):
            payload = {"session_id": session_id, "aid": aid, "type": etype}
            resp = requests.post(f"{API_URL}/api/event", json=payload)
            if resp.status_code == 200:
                st.session_state["last_rec"] = resp.json()
                st.session_state["last_session_id"] = session_id
                st.success("Event sent!")
            else:
                st.error(f"Error: {resp.text}")

    with col_b:
        if "last_rec" in st.session_state:
            res = st.session_state["last_rec"]
            s_id = st.session_state["last_session_id"]
            st.write(f"**Model used:** `{res['model_used']}` | **Latency:** `{res['latency_ms']}ms`")
            
            recs = res["recommendations"]
            t1, t2, t3 = st.tabs(["Clicks", "Carts", "Orders"])
            with t1: st.write(recs.get("clicks", []))
            with t2: st.write(recs.get("carts", []))
            with t3: st.write(recs.get("orders", []))
            
            # Show session history
            s_resp = requests.get(f"{API_URL}/api/session/{s_id}")
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                st.write("**Current Session History:**")
                st.dataframe(pd.DataFrame(s_data["events"]), use_container_width=True)
        else:
            st.write("Send an event to see recommendations here.")

st.markdown("---")
st.caption("OTTO Recommender System - Real-time Pipeline Monitoring")
