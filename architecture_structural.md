# architecture_structural.md — One Chatbot, Two Brands (MarkGrid.ai & Two99)

Describes the code as built. To run it, see `README.md` or `explain.md`.

## 1. Layout

```
BrandBridge AI/
├── backend/
│   ├── config.py        .env + brand JSON loading, leaks(), search_text(), fill()
│   ├── __init__.py      clear message if the wrong Python is used
│   ├── clients.py       Gemini (plain HTTP, retries) and Qdrant: embed(), complete(), qdrant()
│   ├── keyword_search.py  BM25 search used when embedding is unavailable
│   ├── pipeline.py      resolve_brand(), classify(), retrieve(), chat()
│   └── main.py          FastAPI endpoints, CORS, request validation
├── ingestion/ingest.py  page_key(), crawl(), clean(), dedupe(), chunk(), to_rows(), upload() and the CLI
├── brands/
│   ├── markgrid.json    brand profile
│   ├── two99.json       brand profile
│   └── shared.json      intent labels, prompts, fixed replies
├── widget/widget.js     Shadow DOM widget
├── demo/{markgrid,two99}/   index.html + config.js (backend URL)
├── tests/test_chat.py   offline tests
├── data/                git-ignored: extracted/<brand>.json, qdrant/ (local storage)
├── sample.md            test questions with expected answers
├── .env / .env.example  settings
├── requirements.txt     backend, ingestion and test packages
├── start.bat            starts the backend and both demo pages (Windows)
└── vercel.json          backend deployment
```

## 2. Configuration

Every `.env` key is listed in `.env.example`; a missing one raises `KeyError` when it is read.

| Keys | Purpose |
|---|---|
| `GEMINI_API_KEY`, `LLM_BASE_URL`, `MODEL_MAIN`, `MODEL_INTENT`, `EMBED_MODEL`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT` | Gemini, over HTTP. Google's own address contains `/openai/`; no OpenAI key or package is used |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_TIMEOUT` | Qdrant Cloud and its request timeout in seconds; an empty URL means local storage |
| `QDRANT_PATH` | Local storage folder |
| `ORIGIN_BRAND_MAP` | Allowlist of `origin=brand` pairs; also the CORS list |
| `TOP_K`, `MIN_SCORE` | Retrieval |
| `MAX_MESSAGE_CHARS`, `HISTORY_TURNS` | Chat limits (`HISTORY_TURNS` counts messages) |
| `MAX_PAGES`, `CRAWL_DELAY`, `MIN_PAGE_CHARS`, `COMMON_SHARE`, `COMMON_MIN_PAGES`, `CHUNK_CHARS`, `CHUNK_OVERLAP`, `EMBED_BATCH`, `EMBED_DELAY` | Ingestion |

Brand profile fields: `name`, `collection`, `url`, `contact`, `terms` (regexes that identify this brand,
used for leak checks on other brands), `color`, `tone`, `relation`, `welcome`, `suggestions`, `topics` (products, used by the intent model),
`skip_pages` (URL parts never crawled) and `listing_pages` (URL parts followed for links but not stored).

## 3. API

| Endpoint | Behaviour |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /widget.js` | The widget |
| `GET /config?site=` | Name, color, welcome, suggestions and limits for the widget |
| `POST /chat` | Answer a message |

`POST /chat` request and response:

```json
{"site": "markgrid", "message": "What do you do?", "history": [{"role": "user", "content": "..."}]}
```
```json
{"brand": "markgrid", "intent": "brand", "reply": "...", "suggestions": []}
```

`suggestions` is filled only for greetings. Errors: 403 site/origin mismatch (`/config` and `/chat`),
422 invalid body, 503 Gemini busy or limited, 500 other failure. The widget shows the message. The server keeps no session; the widget sends recent history.

## 4. Chat flow

```
resolve_brand(site, Origin) ── mismatch ──► 403
        │
classify (intent model; unknown label → brand)
        ├─ other_brand / related / off_topic / injection ──► fixed reply
        ├─ greeting ───────────────► answer model, no retrieval ─┐
        └─ brand / compare ──► retrieve from brand collection    │
                                 │  (keyword search if Gemini    │
                                 │   embedding fails)            │
                                 ├─ no match ──► fallback        │
                                 └─ answer model ────────────────┤
                                                                 ▼
                              leak check ── leak ──► retry once ──► fallback
                                                                 │
                                                               reply
```

Retrieval includes the previous user message, so follow-up questions work. Compare questions are replaced by
`compare_question` from `shared.json`. `search_text()` adds the
brand name and removes other brands' names before embedding, so vague questions match well.

## 5. Ingestion flow

1. **Crawl:** breadth-first from the brand `url`, same host only, follows robots.txt and its crawl delay,
   honours `skip_pages` and `listing_pages`.
2. **Clean:** drops navigation, headers, scripts, forms, duplicate lines and lines naming the other brand. Keeps
   footers and the emails and phone numbers inside links.
3. **Save:** page text goes to `data/extracted/<brand>.json`.
4. **Dedupe:** pages saved twice (http/https, trailing slash, same text) are dropped. Lines found on more than `COMMON_SHARE` of pages (and more than `COMMON_MIN_PAGES`) are removed
   from each page and stored once as a site-wide page.
5. **Chunk:** `CHUNK_CHARS` characters with `CHUNK_OVERLAP` overlap; later chunks start with the page title.
   Chunks are ordered by address length, so core pages mostly come before articles.
6. **Embed and upload:** `EMBED_BATCH` chunks at a time, with `EMBED_DELAY` seconds between. Each batch is saved
   at once. IDs come from model + URL + text, so chunks already stored are skipped and a stopped upload resumes.
7. **Clean up:** outdated chunks are removed only after every new chunk is saved. Until then old and new coexist.

Payload: `brand`, `url`, `text` (cosine distance). `--dry-run` stops after chunking and needs no keys;
`--cached` starts from the saved text.

## 6. Widget

Loaded by one script tag; the API address is the script's own origin. It fetches `/config`, renders in
Shadow DOM, and inserts text with `textContent`/`append` so replies cannot inject HTML. History lives in
page memory. If `/config` fails, the widget is not shown.

## 7. Brand separation

| Layer | Protection |
|---|---|
| Request | Origin allowlist decides the brand; message text cannot change it |
| Storage | Separate crawls and collections; other-brand lines removed |
| Retrieval | Only the resolved brand's collection is queried |
| Prompt | Current-brand-only rules; context treated as data |
| Output | Leak check on every generated reply |

## 8. Deployment

Three Vercel projects: repo root (backend), `demo/markgrid`, `demo/two99`. Qdrant Cloud is required;
ingestion runs locally. Vercel installs the whole `requirements.txt`, including ingestion and test packages.

## 9. Status and limits

- 29 offline tests; Gemini is faked and Qdrant runs in memory.
- Checked with real Gemini answers on both brands, and through the widget in Chrome. Not yet tested: Vercel, and
  the `sample.md` questions on the new data.
- Upload of the full sites is incomplete: MarkGrid 960 of 3,572 chunks, Two99 0 of 1,151 (24 November 2026).
- Gemini's free embedding limit (1,000 a day) is shared by ingestion and the chatbot; when it runs
  out, the chatbot uses keyword search. Its index loads once, so restart the backend after ingestion.
- `Origin` can be faked outside browsers; there is no rate limiting.
- The leak check matches brand names, not every product name.
