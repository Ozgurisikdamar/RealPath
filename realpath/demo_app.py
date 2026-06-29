"""realpath interactive demo (Streamlit).

    streamlit run realpath/demo_app.py

Local-first: everything runs against a local DuckDB file. Nothing leaves the machine.
"""
from __future__ import annotations

import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd
import streamlit as st

from realpath.engine import connect
from realpath.explain import explain_entity, format_card
from realpath.templates import churn_pql, forecast_pql, fraud_pql

st.set_page_config(page_title="realpath.dev", layout="wide")


@st.cache_resource(show_spinner=False)
def get_engine(db_path: str):
    return connect(db_path)


@st.cache_data(show_spinner=True)
def run_prediction(db_path: str, query: str, calibrate: bool = False):
    eng = get_engine(db_path)
    res = eng.predict(query, evaluate=True, calibrate=calibrate)
    imp = res.global_importance(top_n=12)
    return {
        "pql": res.task.raw or res.task.column_label(),
        "task_type": res.task.task_type,
        "entity_key": res.entity_key,
        "metrics": res.metrics,
        "reliability": res.reliability() if calibrate else {},
        "predictions": res.predictions,
        "importance": imp,
        "_res": res,
    }


st.title("realpath.dev — Neural Database Predictive Engine")
st.caption("Açık kaynak · self-host · **local-first** — veriniz makinenizden çıkmaz.")

with st.sidebar:
    st.header("Veritabanı")
    default_db = str(Path(__file__).resolve().parent.parent / "data" / "shop.duckdb")
    db_path = st.text_input("DuckDB yolu", value=default_db)
    if not Path(db_path).exists():
        st.warning("DB bulunamadı. `python data/make_sample_db.py` ile oluşturun.")
        st.stop()
    eng = get_engine(db_path)
    st.subheader("Şema & FK grafiği")
    for t in eng.schema.tables.values():
        st.markdown(f"**{t.name}**  ·  pk=`{t.primary_key}`  ·  time=`{t.time_index}`")
    st.code("\n".join(str(fk) for fk in eng.schema.foreign_keys), language="text")

st.subheader("1) Bir tahmin sorun")
calibrate = st.checkbox(
    "Olasılık kalibrasyonu (isotonic) — Brier/ECE göster",
    value=False,
    help="Sınıflandırma olasılıklarını held-out isotonic ile kalibre eder. ROC-AUC korunur.",
)
tabs = st.tabs(["Doğal dil / PQL", "Şablonlar"])
query = None
with tabs[0]:
    q = st.text_area(
        "Düz dille (Türkçe/İngilizce) ya da PQL yazın:",
        value="gelecek 30 günde işlem yapmayacak müşterileri bul",
        height=80,
    )
    if st.button("Tahmin et", type="primary"):
        query = q
with tabs[1]:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Churn (müşteri kaybı)"):
            query = churn_pql("customers", "customer_id", "transactions", 30)
    with c2:
        if st.button("Talep tahmini (ürün)"):
            query = forecast_pql("products", "product_id", "transactions", "quantity", 2)
    with c3:
        if st.button("İade riski (müşteri)"):
            query = fraud_pql("customers", "customer_id", "returns", 30)

if query:
    out = run_prediction(db_path, query, calibrate)
    st.session_state["out"] = out
    st.session_state["db_path"] = db_path

out = st.session_state.get("out")
if out:
    st.subheader("2) Sonuç")
    st.code(out["pql"], language="sql")
    cols = st.columns(len(out["metrics"]) or 1)
    for (k, v), col in zip(out["metrics"].items(), cols):
        col.metric(k, f"{v:.4f}")
    rel = out.get("reliability") or {}
    if rel:
        st.caption("🎯 Kalibrasyon kalitesi (düşük = iyi): "
                   + "  ·  ".join(f"**{k.upper()}** {v:.4f}" for k, v in rel.items()))

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("**Tahminler** (skora göre)")
        asc = out["task_type"] == "regression"
        st.dataframe(out["predictions"].sort_values("score", ascending=False).head(20),
                     width="stretch", hide_index=True)
    with right:
        st.markdown("**En etkili sürücüler** (global, gain)")
        imp = out["importance"]
        if not imp.empty:
            chart_df = imp.set_index("feature")["gain"]
            st.bar_chart(chart_df)

    st.subheader("3) Neden? — açıklanabilirlik (join-yolu provenance)")
    res = out["_res"]
    ids = out["predictions"][out["entity_key"]].tolist()
    sel = st.selectbox("Bir entity seçin:", ids[:200])
    if sel is not None:
        score = float(out["predictions"].set_index(out["entity_key"]).loc[sel, "score"])
        contribs = explain_entity(res.model, res.X, sel, top_n=6)
        st.code(format_card(sel, score, contribs, out["task_type"]), language="text")
        if contribs:
            st.dataframe(pd.DataFrame([
                {"feature": c.feature, "value": c.value,
                 "tables": " -> ".join(c.tables), "agg": c.agg, "katki": round(c.weight, 4)}
                for c in contribs
            ]), width="stretch", hide_index=True)
