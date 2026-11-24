"""Keyword (BM25) search over a brand's stored chunks.
Used only when the embedding service is unavailable, so the chat keeps working."""
import math
import re
from collections import Counter
from functools import lru_cache

from backend import clients
from backend.config import BRANDS, SHARED, leaks

K1, B = 1.5, 0.75  # standard BM25 constants
LABEL_WEIGHT = 5  # showing a phone number counts more than mentioning phones


def words(text: str) -> list[str]:
    found = re.findall(r"\w+", text.lower())
    return [w for w in found if w not in SHARED["stopwords"]]


def query_words(text: str) -> set[str]:
    return {SHARED["synonyms"].get(w, w) for w in words(text)}


def labels(text: str) -> list[str]:
    """Words such as "phone" for texts that show a number without naming it."""
    return [label for label, pattern in SHARED["patterns"].items() if re.search(pattern, text)]


@lru_cache
def index(brand: str):
    """Loaded once per brand; restart the backend after a new ingestion."""
    payloads, offset, more = [], None, True
    while more:
        points, offset = clients.qdrant().scroll(BRANDS[brand]["collection"], limit=500, offset=offset)
        payloads += [p.payload for p in points if not leaks(brand, p.payload["text"])]
        more = offset is not None
    counts = [Counter(words(p["text"]) + labels(p["text"]) * LABEL_WEIGHT) for p in payloads]
    in_docs = Counter(w for c in counts for w in c)
    average = sum(c.total() for c in counts) / max(len(counts), 1)
    return payloads, counts, in_docs, average


def search(brand: str, query: str, limit: int) -> list[dict]:
    payloads, counts, in_docs, average = index(brand)
    name = set(words(BRANDS[brand]["name"]))  # on every page, so it says nothing about relevance
    terms = {w for w in query_words(query) if w in in_docs and w not in name}
    if not set(words(query)) - name:  # vague question ("What do you do?"): use the home page
        return [p for p in payloads if p["url"] == BRANDS[brand]["url"]][:limit]

    def score(c: Counter) -> float:
        length = K1 * (1 - B + B * c.total() / average)
        return sum(math.log(1 + (len(counts) - in_docs[t] + 0.5) / (in_docs[t] + 0.5))
                   * c[t] * (K1 + 1) / (c[t] + length) for t in terms if t in c)

    scored = sorted(((score(c), i) for i, c in enumerate(counts)), reverse=True)[:limit]
    return [payloads[i] for s, i in scored if s > 0]
