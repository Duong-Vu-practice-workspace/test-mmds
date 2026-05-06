import streamlit as st
import pandas as pd
from pathlib import Path


st.set_page_config(page_title="User Segments", layout="wide")
st.title("👥 User Segments")

st.markdown("### Clustering Results (K-Means)")

segments_data = pd.DataFrame({
    "Segment": ["Heavy Browser", "Quick Buyer", "Window Shopper", "Cart Abandoner"],
    "Count": [50000, 30000, 15000, 5000],
    "Avg Session Length": [15.2, 3.1, 8.5, 12.3],
    "Conversion Rate": [0.12, 0.85, 0.05, 0.25],
})
st.table(segments_data)

st.markdown("---")
st.markdown("### Segment Visualization")

import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(12, 4))

segments = ["Heavy Browser", "Quick Buyer", "Window Shopper", "Cart Abandoner"]
counts = [50000, 30000, 15000, 5000]

axes[0].pie(counts, labels=segments, autopct='%1.1f%%')
axes[0].set_title("Segment Distribution")

session_lengths = [15.2, 3.1, 8.5, 12.3]
axes[1].bar(segments, session_lengths)
axes[1].set_title("Avg Session Length by Segment")
axes[1].set_ylabel("Events per Session")
plt.xticks(rotation=45)

st.pyplot(fig)

st.markdown("---")
st.markdown("### Segment Profiles")

segment = st.selectbox("Select Segment", segments_data["Segment"].tolist())

if segment == "Heavy Browser":
    st.markdown("""
    - **Characteristics**: Long sessions, many clicks, low conversion
    - **Avg Session Length**: 15.2 events
    - **Conversion Rate**: 12%
    - **Recommendation Strategy**: Show variety, compare features
    """)
elif segment == "Quick Buyer":
    st.markdown("""
    - **Characteristics**: Short sessions, quick decisions, high conversion
    - **Avg Session Length**: 3.1 events
    - **Conversion Rate**: 85%
    - **Recommendation Strategy**: Show deals, bestsellers
    """)
elif segment == "Window Shopper":
    st.markdown("""
    - **Characteristics**: Medium sessions, browsing behavior, very low conversion
    - **Avg Session Length**: 8.5 events
    - **Conversion Rate**: 5%
    - **Recommendation Strategy**: Recommendations may not help much
    """)
else:
    st.markdown("""
    - **Characteristics**: Adds items to cart but doesn't complete order
    - **Avg Session Length**: 12.3 events
    - **Conversion Rate**: 25%
    - **Recommendation Strategy**: Send reminders, offer discounts
    """)

st.markdown("---")
st.markdown("### Run K-Means Clustering")

st.info("K-Means clustering requires Spark. Run the batch job to generate segments.")

if st.button("Run Clustering (Simulated)"):
    with st.spinner("Running K-Means..."):
        import time
        time.sleep(2)
    st.success("Clustering completed! (Simulated)")
    st.balloons()
