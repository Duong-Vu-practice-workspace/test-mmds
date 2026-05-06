import streamlit as st
import json
from pathlib import Path
from typing import List, Tuple
import pandas as pd


st.set_page_config(page_title="Prediction Demo", layout="wide")
st.title("🤖 Prediction Demo")

st.sidebar.header("Configuration")
demo_mode = st.sidebar.selectbox("Demo Mode", ["Covisitation", "SASRec (if available)"])
k = st.sidebar.slider("Top-K predictions", min_value=5, max_value=50, value=20, step=5)

st.markdown("### Enter Session History")

session_input = st.text_area(
    "Session Items (comma-separated item IDs)",
    "12345, 67890, 11111, 22222, 33333",
    height=100,
)

if st.button("Predict"):
    try:
        items = [int(x.strip()) for x in session_input.split(",") if x.strip()]

        if demo_mode == "Covisitation":
            from src.serving.covisitation_recommender import CovisitationRecommender
            recommender = CovisitationRecommender()
            predictions = recommender.recommend_multi_objective(items, top_k=k)

            st.markdown("### Predictions")

            tab1, tab2, tab3 = st.tabs(["Clicks", "Carts", "Orders"])

            with tab1:
                st.markdown(f"**Top-{k} predicted items for clicks:**")
                if predictions["clicks"]:
                    df = pd.DataFrame({
                        "Rank": range(1, len(predictions["clicks"]) + 1),
                        "Item ID": predictions["clicks"],
                    })
                    st.table(df)
                else:
                    st.warning("No covisitation matrix loaded. Run the training step first.")

            with tab2:
                st.markdown(f"**Top-{k} predicted items for carts:**")
                if predictions["carts"]:
                    df = pd.DataFrame({
                        "Rank": range(1, len(predictions["carts"]) + 1),
                        "Item ID": predictions["carts"],
                    })
                    st.table(df)
                else:
                    st.warning("No carts_orders matrix loaded.")

            with tab3:
                st.markdown(f"**Top-{k} predicted items for orders:**")
                if predictions["orders"]:
                    df = pd.DataFrame({
                        "Rank": range(1, len(predictions["orders"]) + 1),
                        "Item ID": predictions["orders"],
                    })
                    st.table(df)
                else:
                    st.warning("No buy2buy matrix loaded.")

        else:
            st.info("SASRec requires a trained model checkpoint (.ckpt file).")
            checkpoint_path = st.text_input("Checkpoint Path", "best_sasrec_model.ckpt")
            if Path(checkpoint_path).exists():
                st.success("Checkpoint found! (SASRec loading not implemented in this demo)")
            else:
                st.warning("Checkpoint not found.")

    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("---")
st.markdown("### Session History")

if "session_history" not in st.session_state:
    st.session_state.session_history = []

if session_input:
    items = [int(x.strip()) for x in session_input.split(",") if x.strip()]
    st.session_state.session_history = items
    st.write(items)

st.markdown("---")
st.markdown("### Batch Prediction from File")

uploaded_file = st.file_uploader("Upload JSONL file (OTTO format)", type=["jsonl"])
if uploaded_file:
    sessions = []
    for line in uploaded_file:
        data = json.loads(line)
        sessions.append(data)

    st.success(f"Loaded {len(sessions)} sessions")

    if st.button("Run Batch Prediction"):
        st.info("Batch prediction would run here...")
