"""All settings come from .env; all brand text comes from brands/*.json."""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

env = os.environ.__getitem__  # fail loudly if a setting is missing


def num(key: str, cast=int):
    return cast(env(key))


SHARED = json.loads((ROOT / "brands/shared.json").read_text("utf-8"))
BRANDS = {p.stem: json.loads(p.read_text("utf-8"))
          for p in (ROOT / "brands").glob("*.json") if p.stem != "shared"}
ORIGINS = dict(pair.strip().rsplit("=", 1) for pair in env("ORIGIN_BRAND_MAP").split(","))

if unknown := set(ORIGINS.values()) - set(BRANDS):
    raise ValueError(f"ORIGIN_BRAND_MAP has unknown brands: {unknown}")


def others(brand: str) -> list[dict]:
    return [b for key, b in BRANDS.items() if key != brand]


def leaks(brand: str, text: str) -> bool:
    """True if the text mentions any other brand."""
    return any(re.search(t, text, re.I) for b in others(brand) for t in b["terms"])


def search_text(brand: str, text: str) -> str:
    """Put the brand name first and drop other brands, so vague questions match well."""
    for t in (t for b in others(brand) for t in b["terms"]):
        text = re.sub(t, "", text, flags=re.I)
    return f"{BRANDS[brand]['name']}: {text}"


def fill(brand: str, template: str, **extra) -> str:
    b, rest = BRANDS[brand], others(brand)
    return template.format(
        name=b["name"], tone=b["tone"], contact=b["contact"], relation=b["relation"],
        topics=", ".join(b["topics"]),
        others=", ".join(o["name"] for o in rest),
        other_links=", ".join(o["url"] for o in rest), **extra)
