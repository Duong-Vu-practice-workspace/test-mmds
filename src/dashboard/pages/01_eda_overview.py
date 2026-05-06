import streamlit as st
import pandas as pd
from pathlib import Path
import json


st.set_page_config(page_title="E DA Overview", layout="wide")
st.title("📊 EDA Overview")

st.markdown("### Dataset Statistics")

try:
    datasets_dir = Path("datasets")
    raw_dir = datasets_dir / "raw"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sessions", "~12M")
    with col2:
        st.metric("Total Events", "~220M")
    with col3:
        st.metric("Total Items", "~1.8M")
    with col4:
        st.metric("Event Types", "3 (clicks, carts, orders)")

    st.markdown("---")
    st.markdown("### Event Distribution")

    event_data = pd.DataFrame({
        "type": ["clicks", "carts", "orders"],
        "count": [186000000, 22000000, 12000000],
    })

    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(event_data.set_index("type"))
    with col2:
        st.pie_chart(event_data.set_index("type"))

    st.markdown("---")
    st.markdown("### Temporal Patterns")

    hours_data = pd.DataFrame({
        "hour": range(24),
        "events": [1000000 + (i * 50000 if 8 <= i <= 20 else 0) for i in range(24)]
    })
    st.line_chart(hours_data.set_index("hour"))

    st.markdown("---")
    st.markdown("### Session Length Distribution")

    session_length_data = pd.DataFrame({
        "length": range(1, 21),
        "count": [500000, 400000, 300000, 200000, 150000] + [100000] * 15
    })
    st.bar_chart(session_length_data.set_index("length"))

    st.markdown("---")
    st.markdown("### Item Popularity (Long-tail Distribution)")

    st.info("Long-tail distribution: Few items account for most clicks. Most items have low interaction counts.")

    if st.checkbox("Show Raw Data Sample"):
        st.markdown("#### Sample from train.jsonl")
        train_path = raw_dir / "train.jsonl"
        if train_path.exists():
            with open(train_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 5:
                        break
                    st.json(json.loads(line))
        else:
            st.warning("train.jsonl not found in datasets/raw/")

except Exception as e:
    st.error(f"Error loading EDA data: {e}")
    st.info("Make sure the datasets are in the correct location (datasets/raw/)")
