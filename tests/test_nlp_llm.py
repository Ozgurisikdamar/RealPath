"""NL -> PQL through the Claude path, without network access or an API key.

``_make_client`` and ``_call_llm`` are replaced with scripted stand-ins, so these tests pin
the contract of ``nl_to_pql`` itself: an LLM reply becomes a query only if it parses, a
reply that doesn't parse is fed back with the parser error for a retry, and when every
attempt fails the offline templates answer instead.
"""
from realpath import nlp
from realpath.pql import parse_pql

CHURN = "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"


def _script(monkeypatch, replies):
    """Stand in for the Anthropic client: return ``replies`` in order, record each prompt."""
    prompts = []
    it = iter(replies)

    def fake_call(client, model, system, user):
        prompts.append(user)
        return next(it)

    monkeypatch.setattr(nlp, "_make_client", lambda: object())
    monkeypatch.setattr(nlp, "_call_llm", fake_call)
    return prompts


def test_unparseable_reply_is_retried_then_accepted(engine, monkeypatch):
    prompts = _script(monkeypatch, ["SELECT 1", f"```\n{CHURN}\n```"])
    res = nlp.nl_to_pql("which customers will stop buying?", engine.schema)
    assert res.source == "llm"
    assert res.pql == CHURN
    parse_pql(res.pql)
    assert len(prompts) == 2
    assert "failed to parse" in prompts[1]          # the parser error went back to the model


def test_reply_that_never_parses_falls_back_to_templates(engine, monkeypatch):
    prompts = _script(monkeypatch, ["SELECT 1"] * 3)
    res = nlp.nl_to_pql("which customers will churn in the next 30 days?", engine.schema)
    assert len(prompts) == 3                        # max_retries=2 -> three attempts
    assert res.source == "template"
    assert "did not parse" in res.note
    assert res.pql == CHURN                         # the offline churn template


def test_no_api_key_uses_templates_without_a_client(engine, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def no_llm(*args, **kwargs):
        raise AssertionError("the LLM must not be called without an API key")

    monkeypatch.setattr(nlp, "_call_llm", no_llm)
    res = nlp.nl_to_pql("which customers will churn in the next 30 days?", engine.schema)
    assert res.source == "template"
    assert res.pql == CHURN
