import logging

from backend import clients, keyword_search
from backend.config import BRANDS, ORIGINS, SHARED, fill, leaks, num, search_text

REPLIES = SHARED["replies"]


def resolve_brand(site: str, origin: str | None) -> str | None:
    """The Origin header decides the brand; the claimed site must agree."""
    brand = ORIGINS.get(origin or "")
    return brand if brand and brand == site else None


def classify(brand: str, messages: list[dict]) -> str:
    label = clients.complete("MODEL_INTENT", fill(brand, SHARED["intent_prompt"]), messages)
    label = label.lower().strip(" .\"'")
    return label if label in SHARED["intents"] else "brand"


def retrieve(brand: str, query: str) -> list[str]:
    text = search_text(brand, query)
    try:
        vector = clients.embed([text], retries=0)[0]
    except clients.GeminiError as e:  # e.g. daily limit reached: search by keywords instead
        logging.warning("embedding unavailable (%s), using keyword search", str(e)[:80])
        found = keyword_search.search(brand, text, num("TOP_K"))
    else:
        found = [p.payload for p in clients.qdrant().query_points(
            BRANDS[brand]["collection"], query=vector,
            limit=num("TOP_K"), score_threshold=num("MIN_SCORE", float)).points]
    return [f"[{p['url']}]\n{p['text']}" for p in found]


def chat(brand: str, message: str, history: list[dict]) -> tuple[str, str]:
    """Returns (intent, reply)."""
    messages = [*history, {"role": "user", "content": message}]
    intent = classify(brand, messages)
    if intent in REPLIES:  # fixed reply: no retrieval, no LLM answer
        return intent, fill(brand, REPLIES[intent])

    if intent == "compare":  # answer only about the current brand
        message, history = fill(brand, SHARED["compare_question"]), []
        messages = [{"role": "user", "content": message}]

    chunks = []
    if intent != "greeting":
        # the previous user turn helps follow-ups such as "and how much is it?"
        previous = [m["content"] for m in history if m["role"] == "user"][-1:]
        chunks = retrieve(brand, "\n".join([*previous, message]))
        if not chunks:
            return intent, fill(brand, REPLIES["fallback"])

    system = fill(brand, SHARED["system_prompt"], context="\n\n".join(chunks))
    for _ in range(2):  # one retry if the reply leaks the other brand
        reply = clients.complete("MODEL_MAIN", system, messages)
        if reply and not leaks(brand, reply):
            return intent, reply
    return intent, fill(brand, REPLIES["fallback"])
