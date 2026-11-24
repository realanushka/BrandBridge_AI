# One Chatbot, Two Brands — MarkGrid.ai & Two99

A single AI chatbot (one backend, one deployment, one embeddable widget) that runs on both **MarkGrid.ai** and **Two99**. On each site it answers only as that brand, and never mixes the two.

## Live Demo

| Site | Test page |
|---|---|
| MarkGrid.ai | `https://<your-markgrid-demo>.vercel.app` |
| Two99 | `https://<your-two99-demo>.vercel.app` |
| Backend API | `https://<your-backend>.vercel.app` |

Both pages load the **same** `widget.js`; only the `data-site` attribute differs.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Backend | Python + FastAPI | Fast to build, clean request validation |
| LLM | Google Gemini (Flash-Lite for intent and answers) | Free tier; called over plain HTTP |
| Embeddings | Gemini `gemini-embedding-001` | Same key, free tier |
| Vector DB | Qdrant (local folder or Qdrant Cloud) | Separate collection per brand, persistent |
| Fallback search | Built-in keyword search (BM25) | Keeps the chat answering when Gemini embedding is limited |
| Scraping | requests + BeautifulSoup | Builds knowledge from each brand's public pages |
| Widget | Vanilla JS + Shadow DOM | One script tag, no framework, styles isolated from host site |
| Hosting | Vercel (backend + 2 test pages) | Free, GitHub deploys, separate domains per site |

---

## Architecture

```
MarkGrid test page ──┐                         ┌── Qdrant: markgrid_kb
                     ├─► widget.js ─► FastAPI ─┤
Two99 test page ─────┘   (data-site)   /chat   └── Qdrant: two99_kb

/chat pipeline:
1. Resolve brand on the server (data-site + Origin check)
2. Classify intent (greeting / brand / other_brand / related / compare / off_topic / injection)
   other_brand / related / off_topic / injection get a fixed reply and stop here
3. Retrieve chunks ONLY from that brand's collection (by meaning; by keywords if embedding fails)
4. Answer with that brand's system prompt + profile (Gemini)
5. Leak check: a reply naming the other brand is regenerated once, then replaced
```

Ingestion runs offline: crawl → clean → save text → dedupe → chunk → embed → upload to the brand's collection.

---

## How the Bot Tells the Two Sites Apart

1. The embed snippet declares the site: `<script src=".../widget.js" data-site="markgrid"></script>`.
2. The backend checks the request's **`Origin` header** against an allowlist mapping each domain to one brand. If they disagree, the request is rejected.
3. The brand is decided **only on the server** — never by the user's message (e.g. "pretend you're Two99") or by the LLM. It is re-checked on every request.

## How Each Brand's Knowledge Is Kept Separate

- **Separate crawls:** each site is scraped on its own, and every chunk is tagged with its brand. Lines naming the other brand are dropped, and repeated menus and footers are stored once.
- **Separate collections:** `markgrid_kb` and `two99_kb` in Qdrant.
- **Hard retrieval filter:** the server queries only the resolved brand's collection, so the LLM never sees the other brand's content.
- **Separate profiles:** one prompt template (`brands/shared.json`) is filled from each brand's own profile (identity, tone, contact link).
- **Output leak check:** replies are scanned for the other brand's name; if found, the reply is regenerated once, then replaced with a safe fallback.

## Cross-Brand & Guardrail Behaviour

MarkGrid is a product built by Two99, so the two are easy to confuse. Rules:

| Visitor asks | Bot does |
|---|---|
| About the other brand ("What does Two99 do?" on MarkGrid) | Politely says it only covers the current brand and links to the other site. No details. |
| "Are MarkGrid and Two99 related?" | One fixed factual line ("MarkGrid is built by Two99"), then steers back. |
| Ambiguous ("What's your pricing?", "Who founded you?") | Always treated as the **current** brand; answered only from its knowledge. |
| Compare the two | Describes only the current brand; doesn't compare. |
| Greetings / small talk | Friendly reply in brand voice + suggested questions. |
| Unrelated topics (recipes, homework, etc.) | Polite decline and redirect. |
| Prompt injection ("ignore your instructions") | Ignored; stays in brand. |
| Info not in knowledge base | Says it doesn't know and shares the contact page. No guessing. |

---

## Setup

**Requirements:** Python 3.11+, Gemini API key (free tier). Qdrant Cloud is needed only for deployment; locally, data is stored in `data/qdrant`.

Windows PowerShell, from the project folder:

```powershell
# 1. Install
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt

# 2. Settings: copy, then set GEMINI_API_KEY (don't overwrite an existing .env)
copy .env.example .env

# 3. Build knowledge bases: ONE TIME per brand (see note below)
venv\Scripts\python -m ingestion.ingest --brand markgrid
venv\Scripts\python -m ingestion.ingest --brand two99

# 4. Run: double-click start.bat, or use three terminals
venv\Scripts\python -m uvicorn backend.main:app --port 8000
venv\Scripts\python -m http.server 5500 -d demo/markgrid
venv\Scripts\python -m http.server 5501 -d demo/two99
```

Open http://localhost:5500 (MarkGrid) and http://localhost:5501 (Two99).

Use either `start.bat` or the three commands, not both. Plain `python` is the global one, so use
`venv\Scripts\python`. Restart the backend after changing code, brand JSON or `.env`, or after ingestion.

Tests (no keys needed): `venv\Scripts\python -m pytest -q`

### When to run ingestion (step 3)

Run it **once per brand**. The data stays in Qdrant, so day to day you only need step 4.
It is done when it prints `uploaded <number> chunks`. Re-run it only if:

- a website's content changed (that brand only);
- you changed `MAX_PAGES` or a `CHUNK_...` / `COMMON_...` setting;
- you switched to a different Qdrant cluster or folder;
- you changed `EMBED_MODEL` (delete the old collection first, as vectors of different models can't be mixed).

You don't type a website address. `--brand markgrid` reads `url` from `brands/markgrid.json`
(https://markgrid.ai/) and saves to its `collection` (`markgrid_kb`); `two99` works the same way.
With local Qdrant, stop the backend first.

| Option | What it does |
|---|---|
| (none) | Crawl, save the text to `data/extracted/<brand>.json`, embed, upload |
| `--cached` | Skip crawling and use the saved text; use this to continue a stopped upload |
| `--dry-run` | Crawl and save the text only; no API keys needed |

**Gemini free tier:** embeddings were limited to **1,000 per day** in November 2026. The full sites are about
4,700 chunks, so a full upload takes several days for free. If it stops with error 429, what is saved stays:
run the same command with `--cached` after the limit resets (midnight Pacific time). Chatbot questions use the
same limit, so **a large upload leaves the chatbot on keyword search until the reset** (see below). Billing on
the Gemini project raises the limit.

**Keyword search fallback:** if embedding fails, the bot searches the same brand's chunks by keywords. Answers can be
weaker, and it switches back by itself.

### Testing the answers

`sample.md` has 86 checks with expected answers for both brands.

### Settings and deployment

All settings are listed in `.env.example`. `ORIGIN_BRAND_MAP` is the site allowlist, as `origin=brand` pairs.

**Deploy:** fill in `QDRANT_URL` and `QDRANT_API_KEY` and run ingestion → push to GitHub → import three Vercel projects (repo root, `demo/markgrid`, `demo/two99`) → add the `.env` variables to the backend project with the real URLs in `ORIGIN_BRAND_MAP` → put the backend URL in both `demo/*/config.js` files.

See `explain.md` for a detailed walkthrough.

## Project Structure

```
backend/      FastAPI app: brand resolution, intent, retrieval, keyword fallback, answer, leak check
start.bat     Starts the backend and both demo pages
ingestion/    Crawl, clean, dedupe, chunk, embed, upload per brand
brands/       Brand profiles (markgrid, two99) + shared prompts and replies, all JSON
widget/       widget.js (embeddable chat widget)
demo/         Two test pages, one styled per brand
tests/        Offline tests
data/         Extracted text and local Qdrant storage (git-ignored)
sample.md     Test checks with expected answers
explain.md    Detailed walkthrough
architecture_structural.md  How the code is organised
```

## Known Limitations

- Knowledge is a snapshot from the crawl date; re-run ingestion to refresh. `MAX_PAGES` (1000) caps each crawl.
- Upload status on 24 November 2026: MarkGrid 960 of 3,572 new chunks (product, solution and glossary pages in; most articles pending); Two99 0 of 1,151 (still on its original 60 pages).
- Only public website content is used; pages that need JavaScript to show text are not supported.
- Keyword search matches words, not meaning, so its answers can be weaker.
- The leak check looks for brand names (`terms` in the brand JSON).
- Non-browser clients can fake `Origin`, and there is no rate limiting.
- `MIN_SCORE` filters little with Gemini embeddings, because unrelated text also scores around 0.5. "I don't know" replies rely on the prompt.
- The Gemini free tier has per-minute and per-day limits (visitors see "I'm a little busy" when one blocks a reply), and written replies take about 5-15 seconds.
- The Vercel deployment has not been tested yet.
