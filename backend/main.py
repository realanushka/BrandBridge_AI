import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend import combined, keyword_search, pipeline
from backend.clients import GeminiError
from backend.config import BRANDS, ORIGINS, ROOT, SHARED, SITES, num

def preload():
    """Load the keyword indexes early, so the first fallback question isn't slow."""
    for brand in BRANDS:
        try:
            keyword_search.index(brand)
        except Exception as e:
            logging.warning("keyword index for %s not loaded: %s", brand, e)


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=preload, daemon=True).start()
    yield


app = FastAPI(title="BrandBridge AI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(ORIGINS),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    site: str
    message: str = Field(min_length=1, max_length=num("MAX_MESSAGE_CHARS"))
    history: list[Turn] = []


def require_brand(site: str, origin: str | None) -> str:
    brand = pipeline.resolve_brand(site, origin)
    if not brand:
        raise HTTPException(403, "Site and origin do not match")
    return brand


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/widget.js")
def widget():
    return FileResponse(ROOT / "widget/widget.js", media_type="application/javascript")


@app.get("/config")
def config(site: str, origin: str | None = Header(None)):
    b = SITES[require_brand(site, origin)]
    return {k: b[k] for k in ("name", "color", "welcome", "suggestions")} | {
        "maxChars": num("MAX_MESSAGE_CHARS"), "historyTurns": num("HISTORY_TURNS")}


@app.post("/chat")
def chat(req: ChatRequest, origin: str | None = Header(None)):
    brand = require_brand(req.site, origin)
    limit, turns = num("MAX_MESSAGE_CHARS"), num("HISTORY_TURNS")
    history = [{"role": t.role, "content": t.content[:limit]} for t in req.history[-turns:]]
    try:
        if brand in BRANDS:
            intent, reply = pipeline.chat(brand, req.message, history)
            suggestions = BRANDS[brand]["suggestions"] if intent == "greeting" else []
        else:
            intent, reply, suggestions = combined.chat(req.message, history)
    except GeminiError as e:
        logging.error("Gemini error %s", e)
        raise HTTPException(503, SHARED["errors"]["busy" if e.busy else "failed"])
    except Exception:
        logging.exception("chat failed")
        raise HTTPException(500, SHARED["errors"]["failed"])
    return {"brand": brand, "intent": intent, "reply": reply, "suggestions": suggestions}
