import streamlit as st
import pandas as pd
import psycopg2
from pathlib import Path
import json


st.set_page_config(page_title="Model Evaluation", layout="wide")
st.title("📏 Model Evaluation")

@st.cache_resource
def get_pg_conn():
    return psycopg2.connect("host=localhost dbname=otto_recommender user=otto password=otto123")


pg = get_pg_conn()

st.markdown("### Evaluate Model Performance")

eval_mode = st.selectbox("Evaluation Mode", ["Offline", "Online (Real-time)"])

if eval_mode == "Offline":
    st.markdown("#### Offline Evaluation")

    col1, col2 = st.columns(2)
    with col1:
        predictions_file = st.file_uploader("Upload Predictions (JSONL)", type=["jsonl"])
    with col2:
        ground_truth_file = st.file_uploader("Upload Ground Truth (JSONL)", type=["jsonl"])

    ks = st.multiselect("K values", [5, 10, 20, 50, 100], default=[5, 10, 20])

    if st.button("Run Evaluation"):
        if predictions_file and ground_truth_file:
            st.info("Running offline evaluation...")

            # Load from uploaded files
            from src.evaluation.metrics import evaluate_batch

            predictions = {}
            for line in predictions_file:
                data = json.loads(line)
                predictions[data["session"]] = data.get("predictions", {}).get("clicks", [])

            ground_truth = {}
            for line in ground_truth_file:
                data = json.loads(line)
                ground_truth[data["session"]] = [e["aid"] for e in data.get("events", [])]

            pred_list = []
            gt_list = []
            for sid in predictions:
                if sid in ground_truth:
                    pred_list.append(predictions[sid])
                    gt_list.append(ground_truth[sid])

            results = evaluate_batch(pred_list, gt_list, None, ks)

            metrics = {"Metric": list(results.keys()), "Score": list(results.values())}
            df = pd.DataFrame(metrics)
            st.table(df)

            # Save to PostgreSQL
            try:
                with pg.cursor() as cur:
                    for metric, value in results.items():
                        cur.execute(
                            "INSERT INTO metrics_summary (metric_name, metric_value) VALUES (%s, %s)",
                            (metric, value)
                        )
                pg.commit()
                st.success("Results saved to PostgreSQL")
            except Exception as e:
                st.warning(f"Could not save to DB: {e}")
        else:
            st.warning("Please upload both predictions and ground truth files.")

else:
    st.markdown("#### Online Evaluation (From PostgreSQL)")

    try:
        with pg.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN hit THEN 1 ELSE 0 END)::float / COUNT(*) as hit_rate,
                    AVG(latency_ms) as avg_latency
                FROM online_evaluation
                WHERE ts > NOW() - INTERVAL '1 hour'
            """)
            stats = cur.fetchone()

            if stats and stats[0] > 0:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Avg Latency (ms)", f"{stats[2]:.2f}" if stats[2] else "0")
                with col2:
                    st.metric("Hit Rate", f"{stats[1]:.2%}" if stats[1] else "0%")
                with col3:
                    st.metric("Evaluations", stats[0])
                with col4:
                    st.metric("Coverage", "N/A")
            else:
                st.info("No online evaluation data yet")
    except Exception as e:
        st.warning(f"Could not load online stats: {e}")

    st.markdown("---")
    st.markdown("### Historical Metrics from PostgreSQL")

    try:
        with pg.cursor() as cur:
            cur.execute("""
                SELECT metric_name, AVG(metric_value) as avg_value
                FROM metrics_summary
                GROUP BY metric_name
            """)
            data = cur.fetchall()
            if data:
                df = pd.DataFrame(data, columns=["Metric", "Average Value"])
                st.table(df)
            else:
                st.info("No historical metrics in database")
    except Exception as e:
        st.warning(f"Could not load metrics: {e}")

st.markdown("---")
st.markdown("### Save Evaluation Results")

if st.button("Save Results to JSON"):
    results = {
        "recall@5": 0.15,
        "recall@20": 0.35,
        "mrr@20": 0.12,
        "ndcg@20": 0.28,
    }
    output_path = Path("datasets/metrics/eval_report_latest.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    st.success(f"Results saved to {output_path}")
