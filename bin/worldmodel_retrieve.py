#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests

from worldmodel_common import DISCORD_WATCHLIST_HEADER, ROOT, canonicalize_url, iso_date, now_utc, parse_index_entities, read_csv, stable_hash, validate_header

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
REQUEST_TIMEOUT = 20
YT_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
YOUTUBE_CHANNELS = [
    {
        "name": "All-In Podcast",
        "channel_id": "UCESLZhusAkFfsNsApnjF_Cg",
        "source_type": "youtube_channel",
        "matches": ["tesla", "elon", "musk", "robotaxi", "fsd", "ev", "electric vehicle"],
    },
    {
        "name": "The Limiting Factor",
        "channel_id": "UCIFn7ONIJHyC-lMnb7Fm_jw",
        "source_type": "youtube_channel",
        "matches": ["tesla", "4680", "battery", "megapack", "robotaxi", "fsd", "autonomy", "supercharger", "energy storage"],
    },
]


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def safe_get_text(url: str) -> str:
    resp = requests_session().get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def extract_actual_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else href
    return href


def build_seeking_alpha_candidates(name: str, ticker: str) -> list[dict[str, str]]:
    ticker = ticker.strip().upper()
    if not ticker:
        return []
    return [
        {
            "title": f"Seeking Alpha {ticker} symbol page",
            "source_name": "Seeking Alpha",
            "source_type": "seeking_alpha",
            "url": f"https://seekingalpha.com/symbol/{ticker}",
        },
        {
            "title": f"Seeking Alpha {ticker} analysis",
            "source_name": "Seeking Alpha",
            "source_type": "seeking_alpha",
            "url": f"https://seekingalpha.com/symbol/{ticker}/analysis",
        },
        {
            "title": f"Seeking Alpha {ticker} earnings call transcripts",
            "source_name": "Seeking Alpha",
            "source_type": "earnings_transcript",
            "url": f"https://seekingalpha.com/symbol/{ticker}/earnings/transcripts",
        },
    ]


def load_discord_watchlist_candidates(entity: dict[str, object]) -> list[dict[str, str]]:
    watchlist_path = ROOT / "data" / "discord_watchlist.csv"
    if not watchlist_path.exists():
        return []
    validate_header(watchlist_path, DISCORD_WATCHLIST_HEADER)
    terms = entity_terms(entity)
    results: list[dict[str, str]] = []
    for item in read_csv(watchlist_path):
        if str(item.get("status", "active")).strip().lower() not in {"active", ""}:
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        keywords = [part.strip().lower() for part in str(item.get("keywords", "")).split(";") if part.strip()]
        haystack = f"{title} {url} {' '.join(keywords)}".lower()
        if not any(term in haystack for term in terms):
            continue
        results.append({
            "title": title or url,
            "source_name": "Discord",
            "source_type": "discord_watchlist",
            "url": url,
            "notes": str(item.get("notes", "")).strip(),
        })
    return results


def entity_terms(entity: dict[str, object]) -> set[str]:
    terms = {str(entity.get("name", "")).lower(), str(entity.get("slug", "")).lower()}
    ticker = str(entity.get("ticker", "")).strip().lower()
    if ticker:
        terms.add(ticker)
    for keyword in entity.get("search_keywords", []):
        for part in re.split(r"[^a-zA-Z0-9]+", str(keyword).lower()):
            if len(part) >= 3:
                terms.add(part)
    extras = {
        "tesla": {"elon", "musk", "robotaxi", "fsd", "megapack", "supercharger", "4680", "autonomy"},
    }
    terms.update(extras.get(str(entity.get("slug", "")).lower(), set()))
    return {t for t in terms if t}


def fetch_youtube_candidates(entity: dict[str, object], transcript_index: dict[str, dict[str, object]], limit_per_channel: int = 3) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    terms = entity_terms(entity)
    for channel in YOUTUBE_CHANNELS:
        feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel["channel_id"]}'
        try:
            xml_text = safe_get_text(feed_url)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            results.append({
                "entity_slug": str(entity["slug"]),
                "entity_name": entity["name"],
                "title": f'{channel["name"]} feed fetch failed',
                "source_name": channel["name"],
                "source_type": "youtube_channel_error",
                "url": feed_url,
                "published_at": "",
                "retrieved_at": now_utc(),
                "hash": stable_hash(str(entity["slug"]), feed_url, str(exc)),
                "already_logged": False,
                "search_keywords": entity.get("search_keywords", []),
                "notes": f'feed fetch failed: {exc}',
            })
            continue

        selected_here = 0
        for entry in root.findall("atom:entry", YT_NS):
            if selected_here >= limit_per_channel:
                break
            video_id = entry.findtext("yt:videoId", default="", namespaces=YT_NS)
            title = entry.findtext("atom:title", default="", namespaces=YT_NS)
            published = entry.findtext("atom:published", default="", namespaces=YT_NS)
            media_desc = entry.findtext("media:group/media:description", default="", namespaces=YT_NS)
            haystack = f"{title} {media_desc}".lower()
            matched = any(term in haystack for term in terms) or any(term in haystack for term in channel.get("matches", []))
            if not matched:
                continue
            video_url = canonicalize_url(f"https://www.youtube.com/watch?v={video_id}")
            transcript = transcript_index.get(video_id, {})
            results.append({
                "entity_slug": str(entity["slug"]),
                "entity_name": entity["name"],
                "title": title,
                "source_name": channel["name"],
                "source_type": "youtube_transcript" if transcript.get("transcript_available") else "youtube_video",
                "url": video_url,
                "published_at": published,
                "retrieved_at": now_utc(),
                "hash": stable_hash(str(entity["slug"]), video_url, title),
                "already_logged": False,
                "search_keywords": entity.get("search_keywords", []),
                "transcript_available": bool(transcript.get("transcript_available")),
                "transcript_path": transcript.get("transcript_path", ""),
                "video_id": video_id,
            })
            selected_here += 1
    return results


def build_seed_candidates(entity: dict[str, object]) -> list[dict[str, object]]:
    slug = str(entity["slug"])
    name = str(entity["name"])
    ticker = str(entity.get("ticker", "")).strip()
    seeds = [
        {"title": f"{name} Investor Relations", "source_name": name, "source_type": "investor_relations", "url": f"https://www.{slug}.com/investor-relations" if slug != "tesla" else "https://ir.tesla.com"},
    ]
    if slug == "tesla":
        seeds.extend([
            {"title": "Tesla SEC filings", "source_name": "SEC", "source_type": "filing_index", "url": "https://www.sec.gov/edgar/browse/?CIK=1318605&owner=exclude"},
            {"title": "Tesla SEC companyfacts", "source_name": "SEC", "source_type": "sec_companyfacts", "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json"},
            {"title": "Tesla AI", "source_name": "Tesla", "source_type": "official_site", "url": "https://www.tesla.com/AI"},
            {"title": "Tesla Supercharger", "source_name": "Tesla", "source_type": "official_site", "url": "https://www.tesla.com/supercharger"},
        ])
    if ticker or name:
        seeds.extend(build_seeking_alpha_candidates(name, ticker))
        seeds.extend(load_discord_watchlist_candidates(entity))
    return seeds


def dedupe_candidates(candidates: list[dict[str, object]], existing: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    seen = set()
    deduped = []
    for seed in candidates:
        url = canonicalize_url(str(seed["url"]))
        key = (str(seed.get("source_type", "")), url)
        if not url or key in seen:
            continue
        seen.add(key)
        record = dict(seed)
        record["url"] = url
        existing_row = existing.get(url, {})
        record["already_logged"] = url in existing
        record["already_processed"] = str(existing_row.get("used_in_update", "")).lower() == "true"
        record["published_at"] = str(record.get("published_at", ""))
        record["retrieved_at"] = now_utc()
        record["hash"] = stable_hash(str(record.get("entity_slug", "")), url, str(record.get("title", "")))
        deduped.append(record)
    return deduped


def load_transcript_index() -> dict[str, dict[str, object]]:
    path = ROOT / ".worldmodel" / "youtube_transcripts_index.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["video_id"]: item for item in data.get("videos", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect candidate source metadata for active WorldModel entities.")
    parser.add_argument("--all-active", action="store_true")
    parser.add_argument("--since-last-report", action="store_true")
    parser.add_argument("--entity")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    entities_csv = {row["slug"]: row for row in read_csv(ROOT / "data" / "entities.csv")}
    index_entities = parse_index_entities()
    selected_entities = []
    for entity in index_entities:
        slug = str(entity.get("slug", ""))
        if args.entity and slug != args.entity:
            continue
        if args.all_active and str(entity.get("status", "")) != "active":
            continue
        csv_row = entities_csv.get(slug, {})
        entity["ticker"] = csv_row.get("ticker", "")
        selected_entities.append(entity)

    existing = {canonicalize_url(row.get("url", "")): row for row in read_csv(ROOT / "data" / "source_log.csv") if row.get("url")}
    transcript_index = load_transcript_index()
    payload = {"generated_at": now_utc(), "run_date": iso_date(), "entities": []}
    for entity in selected_entities:
        slug = str(entity["slug"])
        candidates: list[dict[str, object]] = []
        for seed in build_seed_candidates(entity):
            seed["entity_slug"] = slug
            seed["entity_name"] = entity["name"]
            seed["search_keywords"] = entity.get("search_keywords", [])
            candidates.append(seed)
        candidates.extend(fetch_youtube_candidates(entity, transcript_index))
        deduped = dedupe_candidates(candidates, existing)
        payload["entities"].append({
            "slug": slug,
            "name": entity["name"],
            "last_report": entity.get("last_report", ""),
            "last_retrieval": entity.get("last_retrieval", ""),
            "candidates": deduped,
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
