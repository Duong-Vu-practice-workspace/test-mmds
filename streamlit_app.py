import json
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import streamlit as st
import torch
import torch.nn as nn
import pytorch_lightning as pl_lightning
from torch.nn import Dropout


@st.cache_data(show_spinner=False)
def load_test_sessions(test_path: Path) -> List[Tuple[int, List[int]]]:
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_path}")

    records = []
    with test_path.open("r", encoding="utf-8") as fin:
        for line in fin:
            row = json.loads(line)
            session_id = row["session"]
            for event in row["events"]:
                if event.get("type") == "clicks":
                    records.append({"session_id": session_id, "ts": event.get("ts"), "aid": int(event.get("aid", 0)) + 1})

    df = pd.DataFrame(records)
    if df.empty:
        return []
    df = df.sort_values(["session_id", "ts"]).reset_index(drop=True)
    sessions = []
    for session_id, group in df.groupby("session_id"):
        sessions.append((session_id, group["aid"].tolist()))
    return sessions


class DynamicPositionEmbedding(nn.Module):
    def __init__(self, max_len: int, dimension: int):
        super().__init__()
        self.max_len = max_len
        self.embedding = nn.Embedding(max_len, dimension)
        self.register_buffer("pos_indices_const", torch.arange(0, max_len, dtype=torch.int))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.shape[1]
        return self.embedding(self.pos_indices_const[-seq_len:]) + x


class SASRec(pl_lightning.LightningModule):
    def __init__(
        self,
        hidden_size,
        dropout_rate,
        max_len,
        num_items,
        batch_size,
        sampling_style,
        topk_sampling=False,
        topk_sampling_k=1000,
        learning_rate=0.001,
        num_layers=2,
        loss="bce",
        bpr_penalty=None,
        optimizer="adam",
        output_bias=False,
        share_embeddings=True,
        final_activation=False,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.dropout_rate = dropout_rate
        self.num_items = num_items
        self.batch_size = batch_size
        self.num_layers = num_layers
        self.max_len = max_len
        self.output_bias = output_bias
        self.share_embeddings = share_embeddings
        self.future_mask = torch.triu(torch.ones(max_len, max_len) * float("-inf"), diagonal=1)
        self.register_buffer("future_mask_const", self.future_mask)
        self.register_buffer("seq_diag_const", ~torch.diag(torch.ones(max_len, dtype=torch.bool)))
        if output_bias and share_embeddings:
            self.item_embedding = nn.Embedding(num_items + 1, hidden_size + 1, padding_idx=0)
        else:
            self.item_embedding = nn.Embedding(num_items + 1, hidden_size, padding_idx=0)
        self.positional_embedding_layer = DynamicPositionEmbedding(max_len, hidden_size)
        if share_embeddings:
            self.output_embedding = self.item_embedding
        elif (not share_embeddings) and output_bias:
            self.output_embedding = nn.Embedding(num_items + 1, hidden_size + 1, padding_idx=0)
        else:
            self.output_embedding = nn.Embedding(num_items + 1, hidden_size, padding_idx=0)
        self.norm = nn.LayerNorm([hidden_size])
        self.input_dropout = Dropout(dropout_rate)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=1,
            dim_feedforward=hidden_size,
            dropout=dropout_rate,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=self.num_layers, norm=self.norm)

    def merge_attn_masks(self, padding_mask: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len = padding_mask.shape
        padding_mask_broadcast = ~padding_mask.bool().unsqueeze(1)
        future_masks = self.future_mask_const[:seq_len, :seq_len].eq(float("-inf"))
        future_masks = future_masks.repeat(batch_size, 1, 1)
        merged_masks = padding_mask_broadcast | future_masks
        diag_masks = self.seq_diag_const[:seq_len, :seq_len].repeat(batch_size, 1, 1)
        return diag_masks & merged_masks

    def forward(self, item_indices: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        att_mask = self.merge_attn_masks(mask)
        items = self.item_embedding(item_indices)
        x = items * torch.sqrt(torch.tensor(self.hidden_size, dtype=torch.float32))
        x = self.positional_embedding_layer(x)
        x = self.encoder(self.input_dropout(x), att_mask)
        return x


@st.cache_resource(show_spinner=False)
def load_model(checkpoint_path: Path) -> SASRec:
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")
    model = SASRec.load_from_checkpoint(checkpoint_path, map_location="cpu")
    model.eval()
    return model


def make_input_tensor(session_aids: List[int], max_len: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    input_ids = session_aids[-max_len:]
    pad_len = max_len - len(input_ids)
    padded = [0] * pad_len + input_ids
    mask = [0.0] * pad_len + [1.0] * len(input_ids)
    return torch.tensor([padded], dtype=torch.long, device=device), torch.tensor([mask], dtype=torch.float32, device=device)


def predict_topk(model: SASRec, session_aids: List[int], k: int, device: torch.device) -> List[int]:
    item_ids, mask = make_input_tensor(session_aids, model.max_len, device)
    with torch.no_grad():
        outputs = model(item_ids, mask)
        last = outputs[:, -1, :]
        logits = last.matmul(model.output_embedding.weight.t())
        logits[:, 0] = -float("inf")
        _, indices = torch.topk(logits, k=k, dim=-1)
    return indices.squeeze(0).tolist()


def main():
    st.set_page_config(page_title="OTTO SASRec Demo", layout="wide")
    st.title("OTTO SASRec Demo")

    st.sidebar.header("Cấu hình")
    checkpoint_path = Path(st.sidebar.text_input("Checkpoint path", "best_sasrec_model.ckpt"))
    test_path = Path(st.sidebar.text_input("Test JSONL path", "datasets/otto-recsys-test.jsonl"))
    k = st.sidebar.slider("Top-k predictions", min_value=5, max_value=50, value=20, step=5)
    example_session = st.sidebar.text_input("Session ID (optional)", "")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Hướng dẫn**:\n" \
        "1. Chọn checkpoint SASRec và file test JSONL.\n" \
        "2. Tải session test và chọn session demo.\n" \
        "3. Hiển thị lịch sử click và dự đoán top-k item IDs."
    )

    try:
        sessions = load_test_sessions(test_path)
    except Exception as exc:
        st.error(str(exc))
        return

    st.success(f"Đã load {len(sessions)} test sessions")

    selected_session_idx = 0
    if example_session:
        for idx, (session_id, _) in enumerate(sessions):
            if str(session_id) == example_session:
                selected_session_idx = idx
                break
    else:
        selected_session_idx = st.selectbox("Chọn session demo", list(range(min(50, len(sessions)))), format_func=lambda x: f"#{x} - {sessions[x][0]}")

    session_id, history_aids = sessions[selected_session_idx]
    st.markdown(f"### Session: {session_id}")
    st.markdown("**History (clicks)**")
    st.write(history_aids)

    try:
        model = load_model(checkpoint_path)
    except Exception as exc:
        st.error(str(exc))
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    if st.button("Predict next items"):
        with st.spinner("Đang dự đoán..."):
            preds = predict_topk(model, history_aids, k, device)
        st.markdown("**Predicted top-{} item IDs**".format(k))
        st.write(preds)
        st.table(pd.DataFrame({"rank": list(range(1, len(preds) + 1)), "item_id": preds}))

    st.markdown("---")
    st.markdown("### Ghi chú")
    st.markdown(
        "- Đây là demo hiển thị `session_id`, lịch sử `aid` và top-k dự đoán.\n"
        "- Nếu muốn, bạn có thể map `aid` về tên sản phẩm nếu có dictionary item.\n"
        "- File đầu vào test phải là JSONL giống cấu trúc OTTO: mỗi dòng chứa `session` và `events` với `type` = `clicks`."
    )


if __name__ == "__main__":
    main()
