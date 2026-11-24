"""Offline tests: Gemini is faked and Qdrant runs in memory."""
import os

os.environ["ORIGIN_BRAND_MAP"] = "http://mg=markgrid,http://t9=two99"

import httpx
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from backend import clients, keyword_search
from backend.config import BRANDS, SHARED, search_text
from backend.main import app
from bs4 import BeautifulSoup

from ingestion.ingest import chunk, clean, dedupe, upload

http = TestClient(app)
SITES = [("markgrid", "http://mg", "Two99"), ("two99", "http://t9", "MarkGrid")]


@pytest.fixture
def fake(monkeypatch):
    db = QdrantClient(":memory:")
    state = {"intent": "brand", "replies": ["fine"], "systems": []}

    def complete(model_key, system, messages):
        if model_key == "MODEL_INTENT":
            return state["intent"]
        state["systems"].append(system)
        return state["replies"].pop(0)

    monkeypatch.setattr(clients, "qdrant", lambda: db)
    monkeypatch.setattr(clients, "embed", lambda texts, **o: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(clients, "complete", complete)
    for b in BRANDS:
        upload(b, [{"brand": b, "url": "u", "text": f"secret-{b}"}])
    return state


def ask(site, origin, message="q"):
    return http.post("/chat", json={"site": site, "message": message}, headers={"Origin": origin})


def test_origin_rejections(fake):
    assert ask("two99", "http://mg").status_code == 403
    assert ask("markgrid", "http://evil").status_code == 403
    assert http.post("/chat", json={"site": "markgrid", "message": "q"}).status_code == 403
    assert http.get("/config?site=two99", headers={"Origin": "http://mg"}).status_code == 403


@pytest.mark.parametrize("site,origin,other", SITES)
def test_only_own_knowledge(fake, site, origin, other):
    assert ask(site, origin).json()["reply"] == "fine"
    other_key = next(b for b in BRANDS if b != site)
    assert f"secret-{site}" in fake["systems"][0] and f"secret-{other_key}" not in fake["systems"][0]


@pytest.mark.parametrize("site,origin,other", SITES)
@pytest.mark.parametrize("intent", ["other_brand", "related", "off_topic", "injection"])
def test_fixed_replies_skip_llm(fake, site, origin, other, intent):
    fake["intent"] = intent
    assert BRANDS[site]["name"] in ask(site, origin).json()["reply"]
    assert fake["systems"] == []


@pytest.mark.parametrize("site,origin,other", SITES)
def test_leak_is_regenerated_then_blocked(fake, site, origin, other):
    fake["replies"] = [f"about {other}", "clean"]
    assert ask(site, origin).json()["reply"] == "clean"
    fake["replies"] = [f"about {other}", f"again {other.upper()}"]
    assert BRANDS[site]["contact"] in ask(site, origin).json()["reply"]


def test_greeting_and_no_match(fake, monkeypatch):
    fake["intent"] = "greeting"
    assert ask("markgrid", "http://mg").json()["suggestions"]
    fake["intent"] = "brand"
    monkeypatch.setattr(clients, "embed", lambda t, **o: [[0.0, 1.0]])
    assert BRANDS["markgrid"]["contact"] in ask("markgrid", "http://mg").json()["reply"]


def test_compare_becomes_own_brand_question(fake, monkeypatch):
    fake["intent"], seen = "compare", []
    original = clients.complete
    monkeypatch.setattr(clients, "complete", lambda k, s, m: seen.append(m) or original(k, s, m))
    ask("markgrid", "http://mg", "Compare MarkGrid and Two99")
    assert [m["content"] for m in seen[-1]] == ["What does MarkGrid.ai do?"]


def test_search_text():
    assert search_text("markgrid", "Compare with Two99") == "MarkGrid.ai: Compare with "


def test_validation():
    assert ask("markgrid", "http://mg", "").status_code == 422
    assert ask("markgrid", "http://mg", "x" * 5000).status_code == 422


def test_chunks_cover_all_text():
    text = "".join(chr(65 + i % 26) for i in range(5000))
    assert chunk(text)[-1].endswith(text[-50:]) and chunk("short") == ["short"]
    assert set(SHARED["replies"]) - {"fallback"} <= set(SHARED["intents"])


def test_upload_is_resumable(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(clients, "embed", lambda t, **o: calls.extend(t) or [[1.0, 0.0] for _ in t])
    row = lambda text: {"brand": "markgrid", "url": "u", "text": text}
    upload("markgrid", [row("a"), row("b")])
    upload("markgrid", [row("b"), row("c")])
    assert calls == ["a", "b", "c"]  # "b" is not embedded twice
    points = clients.qdrant().scroll(BRANDS["markgrid"]["collection"])[0]
    assert {p.payload["text"] for p in points} == {"b", "c"}


def test_clean_keeps_contacts_and_drops_other_brand():
    html = "<p>Hi</p><p>By Two99</p><a href='tel:+1'>Call</a><footer>Noida</footer>"
    assert clean("markgrid", BeautifulSoup(html, "lxml")) == "Hi\nCall\n+1\nNoida"


def test_repeated_lines_are_kept_once():
    pages = [{"url": f"u{n}", "text": f"page {n}\nmenu"} for n in range(10)]
    out = dedupe("markgrid", pages)
    assert [p["text"] for p in out] == [f"page {n}" for n in range(10)] + ["menu"]


def test_duplicate_pages_are_dropped():
    pages = [{"url": u, "text": "same"} for u in ("https://a.com/x/", "http://a.com/x/", "http://a.com/x", "https://a.com/copy-of-x/")]
    assert dedupe("markgrid", pages) == [{"url": "https://a.com/x/", "text": "same"}]


@pytest.mark.parametrize("site,origin,other", SITES)
def test_keyword_search_when_embedding_fails(fake, monkeypatch, site, origin, other):
    def limit(*a, **o):
        raise clients.GeminiError("429", busy=True)

    keyword_search.index.cache_clear()
    monkeypatch.setattr(clients, "embed", limit)
    assert ask(site, origin, "secret").json()["reply"] == "fine"
    assert f"secret-{site}" in fake["systems"][0]
    assert all(f"secret-{b}" not in fake["systems"][0] for b in BRANDS if b != site)
    keyword_search.index.cache_clear()


def gemini(monkeypatch, *responses):
    replies, calls = list(responses), []

    def handler(request):
        calls.append(request)
        return replies.pop(0)

    monkeypatch.setattr(clients, "http", lambda: httpx.Client(
        base_url="http://x/v1/", transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(clients.time, "sleep", lambda s: None)
    return calls


def test_gemini_retries_when_busy(monkeypatch):
    ok = httpx.Response(200, json={"choices": [{"message": {"content": " hi "}}]})
    calls = gemini(monkeypatch, httpx.Response(503), ok)
    assert clients.complete("MODEL_MAIN", "s", []) == "hi"
    assert str(calls[0].url) == "http://x/v1/chat/completions"


@pytest.mark.parametrize("status,text,busy", [(429, "limit per day", True), (401, "bad key", False)])
def test_gemini_does_not_retry_hopeless_errors(monkeypatch, status, text, busy):
    calls = gemini(monkeypatch, httpx.Response(status, text=text))
    with pytest.raises(clients.GeminiError) as e:
        clients.embed(["a"])
    assert e.value.busy is busy and len(calls) == 1


def test_busy_message_reaches_visitor(fake, monkeypatch):
    def busy(*a):
        raise clients.GeminiError("429", busy=True)

    monkeypatch.setattr(clients, "complete", busy)
    res = ask("markgrid", "http://mg")
    assert res.status_code == 503 and res.json()["detail"] == SHARED["errors"]["busy"]


def test_phone_is_found_by_keywords():
    assert keyword_search.labels("HR Contact +91-9650354611") == ["phone"]
    assert "phone" in keyword_search.query_words("How can I call?")
