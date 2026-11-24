"""One chat window for all brands: find the brand first, then answer from that brand only."""
import re
from concurrent.futures import ThreadPoolExecutor

from backend import clients, pipeline
from backend.config import BRANDS, COMBINED, SHARED, fill, strip_others

NAMES = " or ".join(b["name"] for b in BRANDS.values())


def mentioned(text: str) -> list[str]:
    """Brands named in the text."""
    return [key for key, b in BRANDS.items() if any(re.search(t, text, re.I) for t in b["terms"])]


def route(messages: list[dict]) -> tuple[str, str]:
    """Returns (label, standalone question)."""
    message = messages[-1]["content"]
    prompt = COMBINED["router_prompt"].format(
        brand_keys=", ".join(BRANDS),
        brand_list="\n".join(f"- {key}: {b['name']} ({', '.join(b['topics'])})" for key, b in BRANDS.items()))
    label, _, question = clients.complete("MODEL_INTENT", prompt, messages).partition("|")
    label = label.strip().lower()
    if label not in (*BRANDS, *COMBINED["labels"]):
        label = "unclear"
    named = mentioned(message)  # a name in the message beats the model's choice of brand
    if len(named) == 1 and (label in BRANDS or label == "unclear"):
        label = named[0]
    question = question.strip()
    if label == "compare" or (label == "both" and (not question or mentioned(question))):
        return "compare", SHARED["compare_question"]
    return label, question or message


def answer(brand: str, question: str) -> str:
    """No chat history is passed on, so one brand's answer can't enter the other's."""
    reply = pipeline.answer(brand, strip_others(brand, question.replace("{name}", BRANDS[brand]["name"])), [], "brand")
    return COMBINED["answer_label"].format(name=BRANDS[brand]["name"], reply=reply)


def chat(message: str, history: list[dict]) -> tuple[str, str, list[str]]:
    """Returns (label, reply, suggestions)."""
    label, question = route([*history, {"role": "user", "content": message}])
    if label in BRANDS:
        return label, answer(label, question), []
    if label in ("both", "compare"):  # each brand is searched and answered separately
        with ThreadPoolExecutor() as pool:
            answers = list(pool.map(lambda b: answer(b, question), BRANDS))
        intro = [COMBINED["compare_intro"]] if label == "compare" else []
        return label, "\n\n".join(intro + answers), []
    reply = fill(next(iter(BRANDS)), COMBINED["replies"][label], names=NAMES)
    suggestions = {"unclear": [b["name"] for b in BRANDS.values()], "greeting": COMBINED["suggestions"]}
    return label, reply, suggestions.get(label, [])
