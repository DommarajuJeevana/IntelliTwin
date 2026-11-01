import json
import pytest

import app.doc_generation as dg
from app.doc_generation import extract_report_request, generate_and_save_report, markdown_to_html


@pytest.mark.parametrize("msg,topic,fname,detail", [
    ("Write a detailed report on federated learning and save it as fl", "federated learning", "fl", "detailed"),
    ("Create a short report about solar energy, save it as 'solar notes'", "solar energy", "solar notes", "brief"),
    ("draft a comprehensive guide on Kubernetes networking", "Kubernetes networking", None, "detailed"),
])
def test_request_parsing(msg, topic, fname, detail):
    r = extract_report_request(msg)
    assert r["topic"] == topic and r["filename"] == fname and r["detail"] == detail


@pytest.mark.parametrize("msg", ["hello", "write an email to my boss", "what is a report", "schedule a meeting tomorrow"])
def test_non_requests(msg):
    assert extract_report_request(msg) is None


def test_markdown_rendering_is_safe():
    out = markdown_to_html("Intro **bold** <script>x</script>\n\n- a\n- b\n\n1. one\n2. two\n\n### Sub")
    assert "<script>" not in out and "<strong>bold</strong>" in out
    assert "<ul><li>a</li><li>b</li></ul>" in out and "<ol>" in out and "<h3>Sub</h3>" in out


WORDS = " ".join(["Federated learning trains models across devices without centralising raw data."] * 20)


def llm(fail_sections=(), truncate=False):
    calls = {"n": 0}
    async def _call(system, prompt, max_tokens=1000):
        calls["n"] += 1
        if "JSON array" in prompt:
            return json.dumps(["Introduction", "Core Concepts", "Privacy"])
        if any(f in prompt for f in fail_sections):
            return "[LLM request failed: boom]"
        return WORDS[:-1] if truncate else WORDS
    _call.calls = calls
    return _call


async def test_detailed_report_saved_verified_and_linked(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(dg, "call_llm", llm())
    req = extract_report_request("Write a detailed report on federated learning and save it as fl")
    res = await generate_and_save_report(u, req)
    assert res["ok"] and res["link"].startswith("/editor/documents/")
    doc = await db.documents.find_one({"user": u["_id"]})
    assert doc["title"] == "fl" and doc["type"] == "report"
    assert doc["content"].count("<h2>") == 3 and len(doc["content"].split()) > 300
    assert str(doc["_id"]) in res["link"]
    assert "no web research" in res["message"] and "References" not in doc["content"]


async def test_failed_section_saves_nothing_and_says_so(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(dg, "call_llm", llm(fail_sections=("Privacy",)))
    res = await generate_and_save_report(u, extract_report_request("write a detailed report on fl and save it as x"))
    assert not res["ok"] and "Privacy" in res["message"] and "nothing was saved" in res["message"]
    assert await db.documents.count_documents({}) == 0


async def test_truncated_output_is_rejected(db, user_factory, monkeypatch):
    u = await user_factory()
    monkeypatch.setattr(dg, "call_llm", llm(truncate=True))
    res = await generate_and_save_report(u, extract_report_request("write a detailed report on fl and save it as x"))
    assert not res["ok"] and await db.documents.count_documents({}) == 0


async def test_duplicate_retry_and_no_overwrite(db, user_factory, monkeypatch):
    u = await user_factory()
    fake = llm()
    monkeypatch.setattr(dg, "call_llm", fake)
    req = extract_report_request("write a detailed report on federated learning and save it as fl")
    a = await generate_and_save_report(u, req)
    n = fake.calls["n"]
    b = await generate_and_save_report(u, req)       # retry
    assert b["document"]["_id"] == a["document"]["_id"] and fake.calls["n"] == n
    assert await db.documents.count_documents({}) == 1
    # a different request with an existing name never overwrites
    c = await generate_and_save_report(u, extract_report_request("write a detailed report on privacy and save it as fl"))
    assert c["document"]["title"] == "fl (2)" and await db.documents.count_documents({}) == 2


async def test_ownership(db, user_factory, monkeypatch):
    a, b = await user_factory("a"), await user_factory("b")
    monkeypatch.setattr(dg, "call_llm", llm())
    await generate_and_save_report(a, extract_report_request("write a detailed report on fl and save it as fl"))
    assert await db.documents.count_documents({"user": b["_id"]}) == 0
