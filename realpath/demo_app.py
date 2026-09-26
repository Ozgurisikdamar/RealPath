"""realpath interactive demo (Streamlit).

    streamlit run realpath/demo_app.py

Local-first: everything runs against a local DuckDB file. Nothing leaves the machine.

The UI speaks English (default) and Turkish: switch in the sidebar or open the app with
``?lang=tr``. The theme lives in ``.streamlit/config.toml`` at the repo root.
"""
from __future__ import annotations

import html
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd
import streamlit as st

from realpath.engine import connect
from realpath.explain import explain_entity, format_card
from realpath.templates import churn_pql, forecast_pql, fraud_pql

LANGS = {"en": "English", "tr": "Türkçe"}

# Every user-visible string, per language. The Turkish strings are the original UI copy.
TEXT = {
    "en": {
        "language": "Language · Dil",
        "caption": "Open source · self-hosted · **local-first** — your data never leaves your machine.",
        "database": "Database",
        "db_path": "DuckDB path",
        "db_missing": "Database not found. Create it with `python data/make_sample_db.py`.",
        "schema": "Schema & FK graph",
        "schema_note": "Keys and time columns are inferred from the data — nothing has to be declared.",
        "step1": "1) Ask a predictive question",
        "calibrate": "Probability calibration (isotonic) — show Brier/ECE",
        "calibrate_help": "Calibrates classification probabilities with a held-out isotonic fit. "
                          "ROC-AUC is preserved.",
        "tab_nl": "Natural language / PQL",
        "tab_templates": "Templates",
        "question": "Ask in plain language (English/Turkish) or write PQL:",
        "question_default": "which customers will churn in the next 30 days?",
        "predict": "Predict",
        "tpl_churn": "Churn (customer loss)",
        "tpl_forecast": "Demand forecast (product)",
        "tpl_fraud": "Return risk (customer)",
        "running": "Compiling the task, synthesizing features and training…",
        "step2": "2) Result",
        "calibration": "🎯 Calibration quality (lower is better): ",
        "predictions": "**Predictions** (by score)",
        "drivers": "**Top drivers** (global, gain)",
        "step3": "3) Why? — explainability (join-path provenance)",
        "pick_entity": "Pick an entity:",
        "contribution": "contribution",
        "metric_accuracy": "Accuracy",
    },
    "tr": {
        "language": "Language · Dil",
        "caption": "Açık kaynak · self-host · **local-first** — veriniz makinenizden çıkmaz.",
        "database": "Veritabanı",
        "db_path": "DuckDB yolu",
        "db_missing": "DB bulunamadı. `python data/make_sample_db.py` ile oluşturun.",
        "schema": "Şema & FK grafiği",
        "schema_note": "Anahtarlar ve zaman sütunları veriden çıkarılır — hiçbir şeyin tanımlanması gerekmez.",
        "step1": "1) Bir tahmin sorun",
        "calibrate": "Olasılık kalibrasyonu (isotonic) — Brier/ECE göster",
        "calibrate_help": "Sınıflandırma olasılıklarını held-out isotonic ile kalibre eder. ROC-AUC korunur.",
        "tab_nl": "Doğal dil / PQL",
        "tab_templates": "Şablonlar",
        "question": "Düz dille (Türkçe/İngilizce) ya da PQL yazın:",
        "question_default": "gelecek 30 günde işlem yapmayacak müşterileri bul",
        "predict": "Tahmin et",
        "tpl_churn": "Churn (müşteri kaybı)",
        "tpl_forecast": "Talep tahmini (ürün)",
        "tpl_fraud": "İade riski (müşteri)",
        "running": "Görev derleniyor, özellikler üretiliyor ve model eğitiliyor…",
        "step2": "2) Sonuç",
        "calibration": "🎯 Kalibrasyon kalitesi (düşük = iyi): ",
        "predictions": "**Tahminler** (skora göre)",
        "drivers": "**En etkili sürücüler** (global, gain)",
        "step3": "3) Neden? — açıklanabilirlik (join-yolu provenance)",
        "pick_entity": "Bir entity seçin:",
        "contribution": "katki",
        "metric_accuracy": "Doğruluk",
    },
}

# Metric keys from Engine._metrics -> display label (language-neutral unless listed in TEXT).
_METRIC_LABELS = {"roc_auc": "ROC-AUC", "mae": "MAE", "rmse": "RMSE"}

# Height of a dataframe showing exactly ten 35 px rows under its header (+2 px border), so the
# scrollable predictions table never ends on a half-cut row.
_TEN_ROWS = 35 * 11 + 2

# Column role -> (tag, colour) in the schema graph.
_ROLE_TAGS = {
    "pk": ("PK", "#4F46E5"),
    "fk": ("FK", "#059669"),
    "time": ("TIME", "#B45309"),
    "numeric": ("num", "#64748B"),
    "categorical": ("cat", "#64748B"),
    "text": ("text", "#94A3B8"),
}

st.set_page_config(page_title="realpath.dev", layout="wide")
# Code blocks show PQL and the ASCII explanation card exactly as typed: no programming ligatures
# ("==", "->", "|-" would otherwise merge into symbols in fonts such as JetBrains Mono).
st.html("<style>pre, code { font-variant-ligatures: none; }</style>")


@st.cache_resource(show_spinner=False)
def get_engine(db_path: str):
    return connect(db_path)


@st.cache_data(show_spinner=False)
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


def schema_dot(schema) -> str:
    """The discovered schema as a Graphviz digraph: one card per table (columns + inferred role),
    parents above children, arrows pointing along each foreign key (child -> parent)."""
    lines = [
        "digraph schema {",
        '  graph [rankdir=TB, bgcolor="transparent", nodesep=0.22, ranksep=0.4, pad=0.04];',
        '  node [shape=plain, fontname="Helvetica", fontsize=11, fontcolor="#0F172A"];',
        '  edge [color="#94A3B8", penwidth=1.4, arrowsize=0.7, dir=back];',
    ]
    for t in schema.tables.values():
        rows = [f'<TR><TD ALIGN="LEFT" COLSPAN="2" BGCOLOR="#EEF2FF"><B>{html.escape(t.name)}</B></TD></TR>']
        for c in t.columns:
            tag, color = _ROLE_TAGS.get(c.role, (c.role, "#64748B"))
            rows.append(
                f'<TR><TD ALIGN="LEFT">{html.escape(c.name)}</TD>'
                f'<TD ALIGN="RIGHT"><FONT COLOR="{color}" POINT-SIZE="9"><B>{html.escape(tag)}</B></FONT></TD></TR>'
            )
        label = (
            '<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" STYLE="ROUNDED" '
            'COLOR="#CBD5E1" BGCOLOR="#FFFFFF">' + "".join(rows) + "</TABLE>>"
        )
        lines.append(f'  "{t.name}" [label={label}];')
    for fk in schema.foreign_keys:
        lines.append(f'  "{fk.parent_table}" -> "{fk.child_table}";')
    # Keep the graph compact enough for the sidebar: a leaf table hanging off a single parent
    # that itself has parents (e.g. returns -> transactions -> customers) sits beside that parent.
    parents = {t: {fk.parent_table for fk in schema.foreign_keys if fk.child_table == t} for t in schema.tables}
    has_children = {fk.parent_table for fk in schema.foreign_keys}
    for t, ps in parents.items():
        if len(ps) == 1 and t not in has_children and parents[next(iter(ps))]:
            lines.append(f'  {{ rank=same; "{next(iter(ps))}"; "{t}"; }}')
    lines.append("}")
    return "\n".join(lines)


def drivers_chart(imp: pd.DataFrame):
    """Horizontal gain bars with the full DFS feature name (= the join path) on the axis."""
    import altair as alt

    data = imp[["feature", "gain", "agg"]]
    return (
        alt.Chart(data)
        .mark_bar(color="#10B981", cornerRadiusEnd=3)
        .encode(
            x=alt.X("gain:Q", title="gain"),
            y=alt.Y("feature:N", sort="-x", title=None, axis=alt.Axis(labelLimit=340),
                    scale=alt.Scale(paddingInner=0.3)),
            tooltip=["feature", alt.Tooltip("gain:Q", format=",.1f"), "agg"],
        )
        .properties(height=340)
    )


# -- language ------------------------------------------------------------
if "lang" not in st.session_state:
    requested = st.query_params.get("lang", "en")
    st.session_state["lang"] = requested if requested in LANGS else "en"
    st.session_state["lang_picker"] = st.session_state["lang"]


def _on_lang_change() -> None:
    picked = st.session_state.get("lang_picker")
    if picked in LANGS:
        st.session_state["lang"] = picked
    else:  # clicking the active option deselects it — keep the current language
        st.session_state["lang_picker"] = st.session_state["lang"]


lang = st.session_state["lang"]
T = TEXT[lang]
if st.query_params.get("lang") != lang:
    st.query_params["lang"] = lang

st.title("realpath.dev — Neural Database Predictive Engine")
st.caption(T["caption"])

with st.sidebar:
    st.segmented_control(
        T["language"], options=list(LANGS), format_func=LANGS.__getitem__,
        key="lang_picker", on_change=_on_lang_change,
    )
    st.header(T["database"])
    default_db = str(Path(__file__).resolve().parent.parent / "data" / "shop.duckdb")
    db_path = st.text_input(T["db_path"], value=default_db)
    if not Path(db_path).exists():
        st.warning(T["db_missing"])
        st.stop()
    eng = get_engine(db_path)
    st.subheader(T["schema"])
    st.graphviz_chart(schema_dot(eng.schema), width="stretch")
    st.caption(T["schema_note"])
    for t in eng.schema.tables.values():
        st.markdown(f"**{t.name}**  ·  pk=`{t.primary_key}`  ·  time=`{t.time_index}`")
    st.code("\n".join(str(fk) for fk in eng.schema.foreign_keys), language="text", wrap_lines=True)

st.subheader(T["step1"])
calibrate = st.checkbox(T["calibrate"], value=False, help=T["calibrate_help"])
tabs = st.tabs([T["tab_nl"], T["tab_templates"]])
query = None
with tabs[0]:
    # one question box per language, so switching language shows that language's example
    q = st.text_area(T["question"], value=T["question_default"], height=80, key=f"question_{lang}")
    if st.button(T["predict"], type="primary"):
        query = q
with tabs[1]:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(T["tpl_churn"]):
            query = churn_pql("customers", "customer_id", "transactions", 30)
    with c2:
        if st.button(T["tpl_forecast"]):
            query = forecast_pql("products", "product_id", "transactions", "quantity", 2)
    with c3:
        if st.button(T["tpl_fraud"]):
            query = fraud_pql("customers", "customer_id", "returns", 30)

if query:
    with st.spinner(T["running"]):
        out = run_prediction(db_path, query, calibrate)
    st.session_state["out"] = out
    st.session_state["db_path"] = db_path

out = st.session_state.get("out")
if out:
    st.subheader(T["step2"])
    st.code(out["pql"], language="sql", wrap_lines=True)
    cols = st.columns(len(out["metrics"]) or 1)
    for (k, v), col in zip(out["metrics"].items(), cols):
        label = T["metric_accuracy"] if k == "accuracy" else _METRIC_LABELS.get(k, k)
        col.metric(label, f"{v:.4f}", border=True)
    rel = out.get("reliability") or {}
    if rel:
        st.caption(T["calibration"]
                   + "  ·  ".join(f"**{k.upper()}** {v:.4f}" for k, v in rel.items()))

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown(T["predictions"])
        st.dataframe(out["predictions"].sort_values("score", ascending=False).head(20),
                     width="stretch", height=_TEN_ROWS, hide_index=True)
    with right:
        st.markdown(T["drivers"])
        imp = out["importance"]
        if not imp.empty:
            st.altair_chart(drivers_chart(imp), width="stretch")

    st.subheader(T["step3"])
    res = out["_res"]
    ids = out["predictions"][out["entity_key"]].tolist()
    sel = st.selectbox(T["pick_entity"], ids[:200])
    if sel is not None:
        score = float(out["predictions"].set_index(out["entity_key"]).loc[sel, "score"])
        contribs = explain_entity(res.model, res.X, sel, top_n=6)
        st.code(format_card(sel, score, contribs, out["task_type"], contribution_label=T["contribution"]),
                language="text")
        if contribs:
            st.dataframe(pd.DataFrame([
                {"feature": c.feature, "value": c.value,
                 "tables": " -> ".join(c.tables), "agg": c.agg, T["contribution"]: round(c.weight, 4)}
                for c in contribs
            ]), width="stretch", hide_index=True)
