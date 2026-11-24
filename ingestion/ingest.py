"""python -m ingestion.ingest --brand <key> [--dry-run] [--cached]
Crawl -> clean -> save text -> chunk -> embed -> upload to the brand's own collection."""
import argparse
import json
import time
import uuid
from collections import Counter
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend import clients
from backend.config import BRANDS, ROOT, env, leaks, num

SKIP_TAGS = ["script", "style", "nav", "header", "form", "noscript", "svg"]


def page_key(url: str) -> str:
    """Same page whether linked as http or https, with or without a trailing slash."""
    return url.split("://", 1)[-1].rstrip("/")


def clean(brand: str, soup: BeautifulSoup) -> str:
    for a in soup.find_all("a", href=True):  # keep emails and phone numbers hidden in links
        kind, _, value = a["href"].partition(":")
        if kind in ("mailto", "tel"):
            a.append("\n" + value.split("?")[0])
    for tag in soup(SKIP_TAGS):
        tag.decompose()
    lines = (" ".join(s.split()) for s in soup.get_text("\n").splitlines())
    # unique lines, minus any that mention the other brand
    return "\n".join(dict.fromkeys(s for s in lines if s and not leaks(brand, s)))


def crawl(brand: str):
    start = BRANDS[brand]["url"]
    host = urlparse(start).netloc
    session = requests.Session()
    robots = RobotFileParser()
    robots.parse(session.get(urljoin(start, "/robots.txt"), timeout=30).text.splitlines())
    delay = max(num("CRAWL_DELAY", float), float(robots.crawl_delay("*") or 0))
    queue, seen, pages = [start], {page_key(start)}, 0
    while queue and pages < num("MAX_PAGES"):
        url = queue.pop(0)
        if (not robots.can_fetch("*", url) or leaks(brand, url)
                or any(part in url for part in BRANDS[brand]["skip_pages"])):
            continue
        time.sleep(delay)
        try:
            res = session.get(url, timeout=30)
        except requests.RequestException as e:
            print("skip", url, e)
            continue
        if (not res.ok or urlparse(res.url).netloc != host
                or "html" not in res.headers.get("content-type", "")):
            print("skip", url, res.status_code)
            continue
        soup = BeautifulSoup(res.content, "lxml")
        for a in soup.find_all("a", href=True):
            link = urldefrag(urljoin(res.url, a["href"]))[0].split("?")[0]
            if urlparse(link).netloc == host and page_key(link) not in seen:
                seen.add(page_key(link))
                queue.append(link.replace("http://", "https://", 1) if start.startswith("https") else link)
        if any(part in url for part in BRANDS[brand]["listing_pages"]):
            continue  # listings are followed for links but hold no content of their own
        text = clean(brand, soup)
        print(len(text), url)
        if len(text) >= num("MIN_PAGE_CHARS"):
            pages += 1
            yield {"url": url, "text": text}


def dedupe(brand: str, pages: list[dict]) -> list[dict]:
    """Drop duplicate pages, and keep repeated menus and footers once, as one site-wide page."""
    # https sorts after http, so it wins when a page was saved under both
    pages = list({page_key(p["url"]): p for p in sorted(pages, key=lambda p: p["url"])}.values())
    # same text under several addresses: keep the shortest address
    pages = list({p["text"]: p for p in sorted(pages, key=lambda p: -len(p["url"]))}.values())
    counts = Counter(line for p in pages for line in p["text"].splitlines())
    limit = max(num("COMMON_MIN_PAGES"), len(pages) * num("COMMON_SHARE", float))
    common = [line for line, n in counts.items() if n > limit]
    drop = set(common)
    out = [{"url": p["url"], "text": "\n".join(x for x in p["text"].splitlines() if x not in drop)}
           for p in pages]
    if common:
        out.append({"url": BRANDS[brand]["url"], "text": "\n".join(common)})
    return [p for p in out if p["text"]]


def chunk(text: str) -> list[str]:
    size, step = num("CHUNK_CHARS"), num("CHUNK_CHARS") - num("CHUNK_OVERLAP")
    return [text[i:i + size] for i in range(0, max(len(text) - num("CHUNK_OVERLAP"), 1), step)]


def to_rows(brand: str, pages: list[dict]) -> list[dict]:
    rows = []
    for p in pages:
        title = p["text"].split("\n", 1)[0]  # later chunks start with the page title for context
        rows += [{"brand": brand, "url": p["url"], "text": c if n == 0 else f"{title}\n{c}"}
                 for n, c in enumerate(chunk(p["text"]))]
    # core pages have short addresses and articles long ones: core content goes first
    return sorted(rows, key=lambda r: len(r["url"]))


def upload(brand: str, rows: list[dict]):
    """Resumable: chunks already stored are not embedded again, so after a
    rate-limit stop the same command continues where it left off."""
    db, name, batch = clients.qdrant(), BRANDS[brand]["collection"], num("EMBED_BATCH")
    wanted = {str(uuid.uuid5(uuid.NAMESPACE_URL, env("EMBED_MODEL") + r["url"] + r["text"])): r
              for r in rows}
    stored, offset, more = set(), None, db.collection_exists(name)
    while more:
        points, offset = db.scroll(name, limit=1000, offset=offset, with_payload=False)
        stored |= {str(p.id) for p in points}
        more = offset is not None
    todo = [i for i in wanted if i not in stored]
    print(len(wanted), "chunks,", len(todo), "new")
    for n in range(0, len(todo), batch):
        if n:
            time.sleep(num("EMBED_DELAY", float))
        ids = todo[n:n + batch]
        vectors = clients.embed([wanted[i]["text"] for i in ids])
        if not db.collection_exists(name):
            db.create_collection(name, VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
        db.upsert(name, [PointStruct(id=i, vector=v, payload=wanted[i]) for i, v in zip(ids, vectors)])
        print("saved", n + len(ids), "of", len(todo))
    if stale := list(stored - wanted.keys()):  # removed only after everything new is saved
        db.delete(name, stale)
    print("uploaded", db.count(name).count, "chunks to", name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True, choices=list(BRANDS))
    ap.add_argument("--dry-run", action="store_true", help="crawl and save text only, no API keys needed")
    ap.add_argument("--cached", action="store_true", help="reuse the saved text instead of crawling")
    args = ap.parse_args()
    saved = ROOT / "data" / "extracted" / f"{args.brand}.json"
    if args.cached:
        pages = [p for p in json.loads(saved.read_text("utf-8"))
                 if not any(part in p["url"] for part in BRANDS[args.brand]["listing_pages"])]
    else:
        pages = list(crawl(args.brand))
        if not pages:
            raise SystemExit("Nothing crawled; collection left unchanged")
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(pages, indent=1, ensure_ascii=False), "utf-8")
    rows = to_rows(args.brand, dedupe(args.brand, pages))
    print(len(pages), "pages,", len(rows), "chunks")
    if not args.dry_run:
        upload(args.brand, rows)
