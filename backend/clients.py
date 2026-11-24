"""Gemini is called over plain HTTP; no OpenAI package or key is used."""
import time
from functools import lru_cache

import httpx
from qdrant_client import QdrantClient

from backend.config import ROOT, env, num


class GeminiError(Exception):
    """Gemini could not answer. `busy` means a limit or overload, so trying later can help."""

    def __init__(self, message: str, busy: bool):
        super().__init__(message)
        self.busy = busy


@lru_cache
def http() -> httpx.Client:
    return httpx.Client(base_url=env("LLM_BASE_URL"), timeout=num("LLM_TIMEOUT"),
                        headers={"Authorization": f"Bearer {env('GEMINI_API_KEY')}"})


def call_gemini(path: str, body: dict, retries: int | None = None) -> dict:
    retries = num("LLM_MAX_RETRIES") if retries is None else retries
    for attempt in range(retries + 1):
        try:
            res = http().post(path, json=body)
        except httpx.TransportError as e:  # timeout or no connection
            error = GeminiError(type(e).__name__, busy=True)
        else:
            if res.is_success:
                return res.json()
            error = GeminiError(f"{res.status_code}: {res.text[:500]}",
                                busy=res.status_code == 429 or res.status_code >= 500)
            if "per day" in res.text:
                break  # a daily limit won't clear by retrying
        if not error.busy:
            break
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    raise error


@lru_cache
def qdrant() -> QdrantClient:
    if url := env("QDRANT_URL"):
        return QdrantClient(url=url, api_key=env("QDRANT_API_KEY"),
                            timeout=num("QDRANT_TIMEOUT"))
    return QdrantClient(path=str(ROOT / env("QDRANT_PATH")), force_disable_check_same_thread=True)


def embed(texts: list[str], retries: int | None = None) -> list[list[float]]:
    data = call_gemini("embeddings", {"model": env("EMBED_MODEL"), "input": texts}, retries)["data"]
    if len(data) != len(texts):  # some models merge a list into one vector
        raise ValueError("EMBED_MODEL must return one vector per text")
    return [d["embedding"] for d in data]


def complete(model_key: str, system: str, messages: list[dict]) -> str:
    res = call_gemini("chat/completions", {
        "model": env(model_key), "messages": [{"role": "system", "content": system}, *messages]})
    return (res["choices"][0]["message"].get("content") or "").strip()
