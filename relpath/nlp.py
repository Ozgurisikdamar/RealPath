"""Natural language -> PQL.

Primary path: a schema-aware prompt to Claude (``anthropic`` SDK), whose output is
*validated by re-parsing* — if it doesn't parse, we feed the error back and retry. This
keeps the LLM honest: a hallucinated query is rejected by the parser, not executed.

Local-first fallback: if ``anthropic`` isn't installed or no API key is set, a deterministic
template matcher handles the common intents (churn / forecast / fraud) entirely offline, so
the "no data leaves your machine" promise holds at the language layer too.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .pql import PQLSyntaxError, parse_pql
from .schema import RelationalSchema

DEFAULT_MODEL = os.environ.get("RELPATH_LLM_MODEL", "claude-sonnet-4-6")

_GRAMMAR = """\
PQL grammar:
  PREDICT  AGG(<table>.<col|*>, <start>, <end>, <unit>) [<op> <value>]
  FOR EACH <entity_table>.<primary_key>
  [WHERE <filter>]      -- filters which target rows count toward the label
  [ASSUMING <filter>]   -- restricts which entities are scored
  AGG  ∈ {COUNT, SUM, AVG, MIN, MAX}     unit ∈ {days, weeks, months}
  op   ∈ {==, !=, >, >=, <, <=}  (present => classification, absent => regression)

Examples:
  -- customers who will NOT transact in the next 30 days (churn):
  PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id
  -- total quantity sold per product over the next 3 months (demand):
  PREDICT SUM(transactions.quantity, 0, 3, months) FOR EACH products.product_id
  -- transactions over 1000 that will be returned within 60 days (fraud/abuse):
  PREDICT COUNT(returns.*, 0, 60, days) > 0 FOR EACH transactions.tx_id ASSUMING transactions.amount > 1000
"""


@dataclass
class NLResult:
    pql: str
    source: str          # 'llm' | 'template'
    note: str = ""


def schema_summary(schema: RelationalSchema) -> str:
    lines = []
    for t in schema.tables.values():
        cols = ", ".join(f"{c.name}({c.role})" for c in t.columns)
        lines.append(f"- {t.name} [pk={t.primary_key}, time={t.time_index}]: {cols}")
    fks = "; ".join(str(fk) for fk in schema.foreign_keys) or "(none)"
    return "TABLES:\n" + "\n".join(lines) + f"\nFOREIGN KEYS: {fks}"


def nl_to_pql(
    question: str,
    schema: RelationalSchema,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> NLResult:
    """Translate a natural-language question to a validated PQL string."""
    client = _make_client()
    if client is None:
        pql = _template_fallback(question, schema)
        return NLResult(pql=pql, source="template",
                        note="LLM unavailable (no anthropic SDK / API key) — used offline templates.")

    system = (
        "You translate natural-language predictive questions into a single PQL statement. "
        "Output ONLY the PQL — no prose, no code fences. Use only tables/columns from the "
        "provided schema. Pick the entity table's primary key for FOR EACH.\n\n" + _GRAMMAR
    )
    convo = f"{schema_summary(schema)}\n\nQUESTION: {question}\n\nPQL:"
    last_err = ""
    for _ in range(max_retries + 1):
        text = _call_llm(client, model, system, convo)
        pql = _strip(text)
        try:
            parse_pql(pql)
            return NLResult(pql=pql, source="llm")
        except (PQLSyntaxError, ValueError) as e:
            last_err = str(e)
            convo += f"\n{pql}\n\nThat PQL failed to parse: {last_err}\nReturn corrected PQL only:"
    # LLM couldn't produce valid PQL — fall back to templates.
    pql = _template_fallback(question, schema)
    return NLResult(pql=pql, source="template",
                    note=f"LLM output did not parse ({last_err}); used offline templates.")


# -- LLM plumbing ------------------------------------------------------
def _make_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        return anthropic.Anthropic()
    except Exception:
        return None


def _call_llm(client, model: str, system: str, user: str) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _strip(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    # keep from PREDICT onward if the model added a preamble
    m = re.search(r"PREDICT\b.*", text, re.IGNORECASE | re.DOTALL)
    return (m.group(0) if m else text).strip()


# -- offline template fallback ----------------------------------------
_CHURN_KW = ["churn", "kayb", "ayrıl", "ayril", "terk", "inactive", "işlem yapmay",
             "islem yapmay", "alışveriş yapmay", "alisveris yapmay", "no longer",
             "stop buying", "hareketsiz", "pasif"]
_FORECAST_KW = ["forecast", "demand", "talep", "taleb", "satış", "satis", "sales",
                "quantity", "miktar", "kaç adet", "kac adet", "ne kadar sat"]
_FRAUD_KW = ["fraud", "doland", "iade", "return", "chargeback", "geri çek", "geri cek",
             "abuse", "suistimal"]
_CUSTOMER_KW = ["müşteri", "musteri", "customer", "user", "kullanıcı", "kullanici", "client"]


def _has(q: str, kws) -> bool:
    return any(k in q for k in kws)


def _event_tables(schema: RelationalSchema):
    return [t for t in schema.tables.values()
            if t.time_index and any(c.role == "fk" for c in t.columns)]


def _parents_of(schema: RelationalSchema, table_name: str):
    return [fk.parent_table for fk in schema.foreign_keys if fk.child_table == table_name]


def _pick_entity(schema, names):
    for t in schema.tables.values():
        if any(n in t.name.lower() for n in names):
            return t
    return None


def _template_fallback(question: str, schema: RelationalSchema) -> str:
    q = question.lower()
    events = _event_tables(schema)
    if not events:
        raise PQLSyntaxError(
            "Couldn't infer a PQL from the question and schema has no event table "
            "(a table with a timestamp + foreign key). Please write PQL directly."
        )
    # biggest event table is a good default 'activity' table
    events_sorted = sorted(events, key=lambda t: len(t.columns), reverse=True)

    if _has(q, _FRAUD_KW):
        # entity = an event table; target = its child with a time index (e.g. returns)
        for ev in events_sorted:
            children = [t for t in events if ev.name in _parents_of(schema, t.name)]
            if children:
                tgt = children[0]
                # customer-level intent ("which customers will return?") -> 2-hop entity
                if _has(q, _CUSTOMER_KW):
                    cust = _pick_entity(schema, ["customer", "user", "client", "account"])
                    if cust and schema.join_path(cust.name, tgt.name):
                        return (f"PREDICT COUNT({tgt.name}.*, 0, 30, days) > 0 "
                                f"FOR EACH {cust.name}.{cust.primary_key}")
                return (f"PREDICT COUNT({tgt.name}.*, 0, 60, days) > 0 "
                        f"FOR EACH {ev.name}.{ev.primary_key}")

    if _has(q, _FORECAST_KW):
        prod = _pick_entity(schema, ["product", "article", "item", "sku"])
        ev = events_sorted[0]
        entity = prod or schema.tables[_parents_of(schema, ev.name)[0]]
        qty = next((c.name for c in ev.columns
                    if c.role == "numeric" and c.name.lower() in
                    ("quantity", "qty", "amount", "total", "sales", "units")), None)
        qty = qty or next((c.name for c in ev.columns if c.role == "numeric"), "*")
        agg = "SUM" if qty != "*" else "COUNT"
        arg = f"{ev.name}.{qty}"
        return f"PREDICT {agg}({arg}, 0, 3, months) FOR EACH {entity.name}.{entity.primary_key}"

    # default: churn
    cust = _pick_entity(schema, ["customer", "user", "client", "account", "member"])
    ev = events_sorted[0]
    if cust and cust.name in _parents_of(schema, ev.name):
        entity = cust
    else:
        parents = _parents_of(schema, ev.name)
        entity = cust or (schema.tables[parents[0]] if parents else None)
    if entity is None:
        raise PQLSyntaxError("Couldn't infer an entity table for churn; please write PQL directly.")
    return f"PREDICT COUNT({ev.name}.*, 0, 30, days) == 0 FOR EACH {entity.name}.{entity.primary_key}"
