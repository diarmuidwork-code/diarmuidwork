#!/usr/bin/env python3
"""Discover Digital and AI events in Ireland for 2026 using only stdlib."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
from typing import Iterable, Optional
from urllib.error import URLError
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

SEARCH_QUERIES = [
    "Ireland AI conference 2026",
    "Ireland digital transformation event 2026",
    "Dublin AI summit 2026",
    "Ireland tech event 2026 artificial intelligence",
    "Cork data AI event 2026",
]

IRELAND_HINTS = {
    "ireland",
    "dublin",
    "cork",
    "galway",
    "limerick",
    "waterford",
    "belfast",
    "kilkenny",
    "sligo",
}

DATE_2026_RE = re.compile(r"\b2026\b")
DATE_RE = re.compile(
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]2026"
    r"|2026[/-]\d{1,2}[/-]\d{1,2}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+2026"
    r"|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+2026"
    r")\b",
    re.IGNORECASE,
)

HREF_RE = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r'<meta[^>]+(?:name="description"|property="og:description")[^>]+content="([^"]*)"',
    re.IGNORECASE,
)
JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass
class Event:
    name: str
    summary: str
    location: str
    dates: str
    link: str


def fetch_html(url: str, timeout: float) -> Optional[str]:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return None
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (URLError, TimeoutError, ValueError):
        return None


def clean_text(text: str) -> str:
    text = TAG_RE.sub(" ", text)
    text = unescape(text)
    return WS_RE.sub(" ", text).strip()


def search_duckduckgo(query: str, timeout: float, limit: int = 12) -> list[str]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    html = fetch_html(url, timeout)
    if not html:
        return []

    links: list[str] = []
    for href in HREF_RE.findall(html):
        parsed = urlparse(href)
        if parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg", [""])[0]
            href = unescape(uddg) if uddg else urljoin("https://duckduckgo.com", href)
        links.append(href)
        if len(links) >= limit:
            break

    return links


def extract_jsonld_events(html: str, source_url: str) -> list[Event]:
    events: list[Event] = []

    def walk(node: object):
        if isinstance(node, dict):
            typ = node.get("@type")
            if typ == "Event" or (isinstance(typ, list) and "Event" in typ):
                yield node
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    for raw_json in JSONLD_RE.findall(html):
        raw_json = raw_json.strip()
        if not raw_json:
            continue
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        for node in walk(data):
            name = str(node.get("name", "")).strip()
            summary = str(node.get("description", "")).strip()
            start = str(node.get("startDate", "")).strip()
            end = str(node.get("endDate", "")).strip()
            location = extract_location(node.get("location"))
            link = str(node.get("url", "")).strip() or source_url
            dates = normalize_dates(start, end)
            if name and dates:
                events.append(
                    Event(
                        name=clean_text(name),
                        summary=clean_text(summary),
                        location=clean_text(location),
                        dates=dates,
                        link=link,
                    )
                )

    return events


def extract_location(location_obj: object) -> str:
    if isinstance(location_obj, str):
        return location_obj
    if isinstance(location_obj, dict):
        pieces = []
        for key in ("name", "address"):
            value = location_obj.get(key)
            if isinstance(value, str):
                pieces.append(value)
            elif isinstance(value, dict):
                for sub in (
                    "streetAddress",
                    "addressLocality",
                    "addressRegion",
                    "postalCode",
                    "addressCountry",
                ):
                    if value.get(sub):
                        pieces.append(str(value[sub]))
        return ", ".join(pieces)
    if isinstance(location_obj, list):
        return "; ".join(extract_location(it) for it in location_obj)
    return ""


def normalize_dates(start: str, end: str) -> str:
    def fmt(dt: str) -> str:
        dt = dt.strip()
        for pattern in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return datetime.strptime(dt, pattern).isoformat()
            except ValueError:
                continue
        return dt

    if start and end:
        return f"{fmt(start)} -> {fmt(end)}"
    return fmt(start or end)


def extract_heuristic_event(html: str, source_url: str) -> list[Event]:
    title_m = TITLE_RE.search(html)
    h1_m = H1_RE.search(html)
    meta_m = META_DESC_RE.search(html)

    name = clean_text(h1_m.group(1) if h1_m else (title_m.group(1) if title_m else ""))
    summary = clean_text(meta_m.group(1) if meta_m else "")
    text = clean_text(html)
    if not summary:
        summary = text[:280]

    dates = ", ".join(dict.fromkeys(DATE_RE.findall(text)[:3]))

    location = ""
    low = text.lower()
    for hint in IRELAND_HINTS:
        if f" {hint} " in f" {low} ":
            location = hint.title()
            break

    if name and dates:
        return [Event(name=name, summary=summary, location=location, dates=dates, link=source_url)]
    return []


def is_ireland_event(event: Event) -> bool:
    blob = " ".join([event.name, event.summary, event.location, event.link]).lower()
    return any(h in blob for h in IRELAND_HINTS)


def is_2026_event(event: Event) -> bool:
    blob = " ".join([event.dates, event.summary, event.name])
    return bool(DATE_2026_RE.search(blob))


def dedupe(events: Iterable[Event]) -> list[Event]:
    seen = set()
    out = []
    for e in events:
        key = (e.name.lower(), e.dates.lower(), e.link.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def crawl_events(max_events: int, pause: float, timeout: float) -> list[Event]:
    candidates: list[str] = []
    for q in SEARCH_QUERIES:
        candidates.extend(search_duckduckgo(q, timeout))
        time.sleep(pause)

    unique_urls = list(dict.fromkeys(candidates))
    events: list[Event] = []

    for url in unique_urls:
        if len(events) >= max_events:
            break
        html = fetch_html(url, timeout)
        if not html:
            continue

        extracted = extract_jsonld_events(html, url)
        if not extracted:
            extracted = extract_heuristic_event(html, url)

        for event in extracted:
            if is_ireland_event(event) and is_2026_event(event):
                events.append(event)

        time.sleep(pause)

    return dedupe(events)[:max_events]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find Digital and AI events taking place in Ireland in 2026."
    )
    parser.add_argument("--max-events", type=int, default=20)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", type=str, default="", help="Optional .json output path")
    args = parser.parse_args()

    events = crawl_events(max_events=args.max_events, pause=args.pause, timeout=args.timeout)
    payload = [asdict(e) for e in events]

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Saved {len(events)} events to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
