#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests

from worldmodel_common import (
    ROOT,
    SOURCE_HISTORY_HEADER,
    SOURCE_REGISTRY_HEADER,
    SUBSTACK_WATCHLIST_HEADER,
    canonicalize_url,
    iso_date,
    now_utc,
    parse_index_entities,
    read_csv,
    stable_hash,
    validate_header,
    write_csv,
)

USER_AGENT = "WorldModelBot/0.3 kabutojira@example.com"
REQUEST_TIMEOUT = 20
YT_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
YOUTUBE_FALLBACK_CHANNEL_IDS = {
    "https://www.youtube.com/@thelimitingfactor": "UCIFn7ONIJHyC-lMnb7Fm_jw",
    "https://www.youtube.com/@allin": "UCESLZhusAkFfsNsApnjF_Cg",
}
SEC_CACHE_DIR = ROOT / ".worldmodel" / "sec"


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    })
    return session


def safe_get_text(url: str) -> str:
    resp = requests_session().get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def safe_get_json(url: str) -> dict[str, object] | list[object]:
    resp = requests_session().get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def cache_json(cache_path: Path, url: str, refresh_seconds: int = 86400) -> dict[str, object] | list[object]:
    try:
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime <= refresh_seconds:
            return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    data = safe_get_json(url)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


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


def build_seeking_alpha_candidates(name: str, ticker: str) -> list[dict[str, object]]:
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


def load_sec_ticker_map() -> dict[str, str]:
    raw = cache_json(SEC_CACHE_DIR / "company_tickers.json", "https://www.sec.gov/files/company_tickers.json")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for item in raw.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        cik = str(item.get("cik_str", "")).strip()
        if ticker and cik:
            result[ticker] = cik.zfill(10)
    return result


def sec_cik_for_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not ticker or "." in ticker:
        return ""
    return load_sec_ticker_map().get(ticker, "")


def sec_archive_base(cik: str, accession: str) -> str:
    compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact}"


def sec_document_url(cik: str, accession: str, filename: str) -> str:
    return f"{sec_archive_base(cik, accession)}/{filename}"


def sec_recent_filings(cik: str) -> list[dict[str, str]]:
    if not cik:
        return []
    data = cache_json(SEC_CACHE_DIR / f"submissions_{cik}.json", f"https://data.sec.gov/submissions/CIK{cik}.json", refresh_seconds=21600)
    if not isinstance(data, dict):
        return []
    filings = data.get("filings", {})
    if not isinstance(filings, dict):
        return []
    recent = filings.get("recent", {})
    if not isinstance(recent, dict):
        return []
    keys = ["filingDate", "form", "accessionNumber", "primaryDocument", "primaryDocDescription"]
    lists = [recent.get(key, []) for key in keys]
    if not all(isinstance(items, list) for items in lists):
        return []
    length = min(len(items) for items in lists)
    rows = []
    for idx in range(length):
        rows.append({
            "filing_date": str(recent["filingDate"][idx]),
            "form": str(recent["form"][idx]),
            "accession": str(recent["accessionNumber"][idx]),
            "primary_document": str(recent["primaryDocument"][idx]),
            "description": str(recent["primaryDocDescription"][idx]),
        })
    return rows


def latest_recent_form(filings: list[dict[str, str]], forms: set[str]) -> dict[str, str] | None:
    for filing in filings:
        if filing.get("form") in forms:
            return filing
    return None


def sec_index_documents(cik: str, accession: str) -> list[dict[str, str]]:
    if not cik or not accession:
        return []
    data = cache_json(
        SEC_CACHE_DIR / f"index_{cik}_{accession.replace('-', '')}.json",
        f"{sec_archive_base(cik, accession)}/index.json",
        refresh_seconds=21600,
    )
    if not isinstance(data, dict):
        return []
    directory = data.get("directory", {})
    if not isinstance(directory, dict):
        return []
    items = directory.get("item", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def sec_exhibit_text(cik: str, accession: str, filename: str) -> str:
    if not cik or not accession or not filename:
        return ""
    cache_path = SEC_CACHE_DIR / f"exhibit_{cik}_{accession.replace('-', '')}_{filename}"
    try:
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime <= 21600:
            return cache_path.read_text(encoding="utf-8")
    except Exception:
        pass
    text = safe_get_text(sec_document_url(cik, accession, filename))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def classify_sec_exhibit(filename: str, text: str) -> tuple[str, str]:
    lower = f"{filename} {text[:4000]}".lower()
    if "production, deliveries" in lower or ("deliveries" in lower and "production" in lower):
        return "delivery_update", "delivery update"
    if "financial results" in lower or "financial summary" in lower or "results of operations" in lower:
        if "update" in lower or "key metrics" in lower or "operational summary" in lower:
            return "investor_presentation", "quarterly update deck"
        return "earnings_release", "earnings release"
    if "presentation" in lower or "shareholder" in lower or "key metrics" in lower or "operational summary" in lower:
        return "investor_presentation", "investor presentation"
    return "official_site", "8-K exhibit"


def build_sec_candidates(entity: dict[str, object]) -> list[dict[str, object]]:
    ticker = str(entity.get("ticker", "")).strip().upper()
    cik = sec_cik_for_ticker(ticker)
    if not cik:
        return []
    name = str(entity.get("name", "")).strip() or ticker
    filings = sec_recent_filings(cik)
    results: list[dict[str, object]] = [
        {
            "title": f"{name} SEC submissions",
            "source_name": "SEC",
            "source_type": "filing_index",
            "url": f"https://data.sec.gov/submissions/CIK{cik}.json",
        },
        {
            "title": f"{name} SEC companyfacts",
            "source_name": "SEC",
            "source_type": "sec_companyfacts",
            "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        },
    ]
    for form in ["10-K", "10-Q"]:
        filing = latest_recent_form(filings, {form})
        if not filing:
            continue
        results.append({
            "title": f"{name} latest {form} ({filing['filing_date']})",
            "source_name": "SEC",
            "source_type": "sec_filing",
            "url": sec_document_url(cik, filing["accession"], filing["primary_document"]),
            "published_at": filing["filing_date"],
            "notes": f"Dynamic SEC discovery from submissions feed; form={form}",
        })
    recent_8k = [filing for filing in filings if filing.get("form") == "8-K"][:4]
    for filing in recent_8k:
        results.append({
            "title": f"{name} 8-K ({filing['filing_date']})",
            "source_name": "SEC",
            "source_type": "sec_filing",
            "url": sec_document_url(cik, filing["accession"], filing["primary_document"]),
            "published_at": filing["filing_date"],
            "notes": f"Dynamic SEC discovery from submissions feed; form=8-K; {filing.get('description', '')}".strip(),
        })
        for item in sec_index_documents(cik, filing["accession"]):
            filename = str(item.get("name", "")).strip()
            if not filename.lower().endswith((".htm", ".html", ".txt")):
                continue
            if "ex99" not in filename.lower() and "exhibit99" not in filename.lower():
                continue
            text = sec_exhibit_text(cik, filing["accession"], filename)
            source_type, label = classify_sec_exhibit(filename, text)
            results.append({
                "title": f"{name} {label} ({filing['filing_date']})",
                "source_name": "SEC",
                "source_type": source_type,
                "url": sec_document_url(cik, filing["accession"], filename),
                "published_at": filing["filing_date"],
                "notes": f"Dynamic SEC exhibit discovery from 8-K accession {filing['accession']}",
            })
    return results


def normalize_substack_feed_url(feed_url: str) -> str:
    feed_url = feed_url.strip()
    if not feed_url:
        return ""
    if not feed_url.startswith(("http://", "https://")):
        feed_url = "https://" + feed_url.lstrip("/")
    parsed = urlparse(feed_url)
    path = parsed.path.rstrip("/")
    if "/p/" not in path and not path.endswith("/feed"):
        feed_url = f"{parsed.scheme}://{parsed.netloc}{path}/feed"
    return canonicalize_url(feed_url)


def parse_substack_pubdate(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone().isoformat()
    except Exception:
        return value


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


def load_source_registry() -> list[dict[str, str]]:
    path = ROOT / "data" / "source_registry.csv"
    validate_header(path, SOURCE_REGISTRY_HEADER)
    return read_csv(path)


def registry_entities(row: dict[str, str]) -> set[str]:
    return {part.strip().lower() for part in str(row.get("entities", "")).split(";") if part.strip()}


def registry_matches_entity(row: dict[str, str], entity: dict[str, object]) -> bool:
    slug = str(entity.get("slug", "")).lower()
    listed = registry_entities(row)
    if slug and slug in listed:
        return True
    terms = entity_terms(entity)
    return bool(listed & terms)


def registry_note(row: dict[str, str]) -> str:
    quality = str(row.get("quality_notes", "")).strip()
    bias = str(row.get("bias_notes", "")).strip()
    freq = str(row.get("retrieval_frequency", "")).strip()
    parts = []
    if quality:
        parts.append(f"quality: {quality}")
    if bias:
        parts.append(f"bias: {bias}")
    if freq:
        parts.append(f"frequency: {freq}")
    return " | ".join(parts)


def load_substack_watchlist_rows() -> list[dict[str, str]]:
    watchlist_path = ROOT / "data" / "substack_watchlist.csv"
    if not watchlist_path.exists():
        return []
    validate_header(watchlist_path, SUBSTACK_WATCHLIST_HEADER)
    return read_csv(watchlist_path)


def load_substack_registry_candidates(entity: dict[str, object], registry_rows: list[dict[str, str]], limit_per_feed: int = 3) -> list[dict[str, object]]:
    terms = entity_terms(entity)
    results: list[dict[str, object]] = []
    for row in registry_rows:
        if str(row.get("platform", "")).strip().lower() != "substack":
            continue
        if not registry_matches_entity(row, entity):
            continue
        publication = str(row.get("name", "")).strip() or "Substack"
        feed_url = normalize_substack_feed_url(str(row.get("url", "")).strip())
        try:
            root = ET.fromstring(safe_get_text(feed_url))
        except Exception as exc:
            results.append({
                "source_id": str(row.get("source_id", "")).strip(),
                "title": f"{publication} feed fetch failed",
                "source_name": publication,
                "source_type": "substack_feed_error",
                "url": feed_url,
                "notes": f"{registry_note(row)} | feed fetch failed: {exc}".strip(" |"),
            })
            continue
        selected_here = 0
        row_terms = registry_entities(row) | {publication.lower()}
        for entry in root.findall("./channel/item"):
            if selected_here >= limit_per_feed:
                break
            title = (entry.findtext("title") or "").strip()
            link = canonicalize_url((entry.findtext("link") or "").strip())
            description = (entry.findtext("description") or "").strip()
            haystack = f"{publication} {title} {description} {' '.join(row_terms)}".lower()
            if not any(term in haystack for term in terms):
                continue
            results.append({
                "source_id": str(row.get("source_id", "")).strip(),
                "title": title or link,
                "source_name": publication,
                "source_type": "substack_post",
                "url": link,
                "published_at": parse_substack_pubdate(entry.findtext("pubDate") or ""),
                "notes": registry_note(row),
            })
            selected_here += 1
    return results


def discover_youtube_feed_url(url: str) -> str:
    canonical = canonicalize_url(url)
    if canonical in YOUTUBE_FALLBACK_CHANNEL_IDS:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={YOUTUBE_FALLBACK_CHANNEL_IDS[canonical]}"
    html = safe_get_text(canonical)
    for pattern in [r'"rssUrl":"([^"]+)"', r'"externalId":"(UC[^"]+)"', r'channelId":"(UC[^"]+)"']:
        match = re.search(pattern, html)
        if not match:
            continue
        value = match.group(1)
        if value.startswith("http"):
            return canonicalize_url(value.replace("\\u0026", "&").replace("\\/", "/"))
        if value.startswith("UC"):
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={value}"
    raise ValueError(f"could not discover YouTube feed for {url}")


def fetch_youtube_registry_candidates(entity: dict[str, object], registry_rows: list[dict[str, str]], transcript_index: dict[str, dict[str, object]], limit_per_channel: int = 3) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    terms = entity_terms(entity)
    for row in registry_rows:
        if str(row.get("platform", "")).strip().lower() != "youtube":
            continue
        if not registry_matches_entity(row, entity):
            continue
        source_name = str(row.get("name", "")).strip() or "YouTube"
        source_id = str(row.get("source_id", "")).strip()
        channel_url = canonicalize_url(str(row.get("url", "")).strip())
        try:
            feed_url = discover_youtube_feed_url(channel_url)
            xml_text = safe_get_text(feed_url)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            results.append({
                "source_id": source_id,
                "entity_slug": str(entity["slug"]),
                "entity_name": entity["name"],
                "title": f"{source_name} feed fetch failed",
                "source_name": source_name,
                "source_type": "youtube_channel_error",
                "url": channel_url,
                "published_at": "",
                "retrieved_at": now_utc(),
                "hash": stable_hash(str(entity["slug"]), channel_url, str(exc)),
                "already_logged": False,
                "search_keywords": entity.get("search_keywords", []),
                "notes": f"{registry_note(row)} | feed fetch failed: {exc}".strip(" |"),
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
            haystack = f"{title} {media_desc} {source_name}".lower()
            if not any(term in haystack for term in terms):
                continue
            video_url = canonicalize_url(f"https://www.youtube.com/watch?v={video_id}")
            transcript = transcript_index.get(video_id, {})
            results.append({
                "source_id": source_id,
                "entity_slug": str(entity["slug"]),
                "entity_name": entity["name"],
                "title": title,
                "source_name": source_name,
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
                "notes": registry_note(row),
            })
            selected_here += 1
    return results


def build_registry_profile_candidates(entity: dict[str, object], registry_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for row in registry_rows:
        platform = str(row.get("platform", "")).strip().lower()
        if platform not in {"x"}:
            continue
        if not registry_matches_entity(row, entity):
            continue
        results.append({
            "source_id": str(row.get("source_id", "")).strip(),
            "title": f"{row.get('name', 'Source')} profile",
            "source_name": str(row.get("name", "")).strip() or platform,
            "source_type": str(row.get("source_type", "")).strip() or f"{platform}_profile",
            "url": canonicalize_url(str(row.get("url", "")).strip()),
            "notes": registry_note(row),
        })
    return results


def build_seed_candidates(entity: dict[str, object], registry_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    slug = str(entity["slug"])
    name = str(entity["name"])
    ticker = str(entity.get("ticker", "")).strip()
    entity_type = str(entity.get("type", "")).strip().lower()
    seeds: list[dict[str, object]] = []
    if entity_type in {"company", "private_company", "supplier", "customer"}:
        seeds.append(
            {
                "title": f"{name} Investor Relations",
                "source_name": name,
                "source_type": "investor_relations",
                "url": f"https://www.{slug}.com/investor-relations" if slug != "tesla" else "https://ir.tesla.com",
            }
        )
    if slug == "tesla":
        seeds.extend([
            {"title": "Tesla AI", "source_name": "Tesla", "source_type": "official_site", "url": "https://www.tesla.com/AI"},
            {"title": "Tesla Supercharger", "source_name": "Tesla", "source_type": "official_site", "url": "https://www.tesla.com/supercharger"},
        ])
    seeds.extend(build_sec_candidates(entity))
    if ticker or name:
        seeds.extend(build_seeking_alpha_candidates(name, ticker))
    seeds.extend(build_registry_profile_candidates(entity, registry_rows))
    seeds.extend(load_substack_registry_candidates(entity, registry_rows))
    return seeds


def history_key(entity_slug: str, url: str) -> str:
    return stable_hash(entity_slug, url)


def load_transcript_index() -> dict[str, dict[str, object]]:
    path = ROOT / ".worldmodel" / "youtube_transcripts_index.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["video_id"]: item for item in data.get("videos", [])}


def load_existing_source_log() -> dict[str, dict[str, str]]:
    rows = read_csv(ROOT / "data" / "source_log.csv")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        entity_slug = str(row.get("entity_slug", "")).strip()
        url = canonicalize_url(str(row.get("url", "")).strip())
        if entity_slug and url:
            result[history_key(entity_slug, url)] = row
    return result


def load_source_history() -> dict[str, dict[str, str]]:
    path = ROOT / "data" / "source_history.csv"
    if not path.exists():
        write_csv(path, [], SOURCE_HISTORY_HEADER)
        return {}
    validate_header(path, SOURCE_HISTORY_HEADER)
    return {str(row.get("history_key", "")).strip(): row for row in read_csv(path) if row.get("history_key")}


def to_int(value: object) -> int:
    try:
        return int(str(value).strip() or "0")
    except Exception:
        return 0


def discovery_state(existing_log: dict[str, str], existing_history: dict[str, str]) -> str:
    if existing_log or existing_history:
        return "already_logged"
    return "new_candidate"


def processing_state(existing_log: dict[str, str], existing_history: dict[str, str]) -> str:
    if existing_log and str(existing_log.get("used_in_update", "")).lower() == "true":
        return "fully_synthesized"
    state = str(existing_history.get("current_state", "")).strip().lower()
    if state == "fully_synthesized":
        return "fully_synthesized"
    if existing_log or existing_history:
        return "logged_unprocessed"
    return "not_synthesized"


def workflow_state(existing_log: dict[str, str], existing_history: dict[str, str]) -> str:
    state = processing_state(existing_log, existing_history)
    if state == "not_synthesized":
        return "new_candidate"
    return state


def dedupe_candidates(candidates: list[dict[str, object]], existing_log: dict[str, dict[str, str]], existing_history: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    seen = set()
    deduped = []
    for seed in candidates:
        entity_slug = str(seed.get("entity_slug", "")).strip()
        url = canonicalize_url(str(seed.get("url", "")))
        key = (str(seed.get("source_type", "")), url)
        if not url or key in seen:
            continue
        seen.add(key)
        record = dict(seed)
        record["url"] = url
        history_id = history_key(entity_slug, url)
        log_row = existing_log.get(history_id, {})
        history_row = existing_history.get(history_id, {})
        record["source_history_key"] = history_id
        record["already_logged"] = bool(log_row or history_row)
        record["already_processed"] = processing_state(log_row, history_row) == "fully_synthesized"
        record["discovery_state"] = discovery_state(log_row, history_row)
        record["processing_state"] = processing_state(log_row, history_row)
        record["workflow_state"] = workflow_state(log_row, history_row)
        record["published_at"] = str(record.get("published_at", ""))
        record["retrieved_at"] = now_utc()
        record["hash"] = stable_hash(entity_slug, url, str(record.get("title", "")))
        deduped.append(record)
    return deduped


def update_source_history(candidates_by_entity: list[dict[str, object]], existing_log: dict[str, dict[str, str]], history_rows: dict[str, dict[str, str]]) -> None:
    now = now_utc()
    for entity in candidates_by_entity:
        slug = str(entity.get("slug", "")).strip()
        raw_candidates = entity.get("candidates", [])
        if not isinstance(raw_candidates, list):
            continue
        for candidate in raw_candidates:
            if not isinstance(candidate, dict):
                continue
            key = str(candidate.get("source_history_key", "")).strip()
            if not key:
                continue
            current = dict(history_rows.get(key, {}))
            log_row = existing_log.get(key, {})
            state = processing_state(log_row, current)
            current.update({
                "history_key": key,
                "source_id": str(candidate.get("source_id", current.get("source_id", ""))).strip(),
                "entity_slug": slug,
                "title": str(candidate.get("title", current.get("title", ""))).strip(),
                "source_name": str(candidate.get("source_name", current.get("source_name", ""))).strip(),
                "source_type": str(candidate.get("source_type", current.get("source_type", ""))).strip(),
                "url": canonicalize_url(str(candidate.get("url", current.get("url", ""))).strip()),
                "first_seen_at": str(current.get("first_seen_at", "")).strip() or now,
                "last_seen_at": now,
                "last_selected_at": str(current.get("last_selected_at", "")).strip(),
                "last_used_at": str(current.get("last_used_at", "")).strip(),
                "times_seen": str(to_int(current.get("times_seen")) + 1),
                "times_selected": str(to_int(current.get("times_selected"))),
                "times_used": str(max(to_int(current.get("times_used")), 1 if state == "fully_synthesized" else 0)),
                "current_state": state,
                "notes": str(candidate.get("notes", current.get("notes", ""))).strip(),
            })
            if state == "fully_synthesized" and not current.get("last_used_at"):
                current["last_used_at"] = str(log_row.get("retrieved_at", "")).strip() or now
            history_rows[key] = current
    ordered = sorted(history_rows.values(), key=lambda row: (row.get("entity_slug", ""), row.get("url", "")))
    write_csv(ROOT / "data" / "source_history.csv", ordered, SOURCE_HISTORY_HEADER)


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

    registry_rows = load_source_registry()
    existing_log = load_existing_source_log()
    existing_history = load_source_history()
    transcript_index = load_transcript_index()
    payload = {"generated_at": now_utc(), "run_date": iso_date(), "entities": []}
    for entity in selected_entities:
        slug = str(entity["slug"])
        candidates: list[dict[str, object]] = []
        for seed in build_seed_candidates(entity, registry_rows):
            seed["entity_slug"] = slug
            seed["entity_name"] = entity["name"]
            seed["search_keywords"] = entity.get("search_keywords", [])
            candidates.append(seed)
        candidates.extend(fetch_youtube_registry_candidates(entity, registry_rows, transcript_index))
        deduped = dedupe_candidates(candidates, existing_log, existing_history)
        payload["entities"].append({
            "slug": slug,
            "name": entity["name"],
            "last_report": entity.get("last_report", ""),
            "last_retrieval": entity.get("last_retrieval", ""),
            "candidates": deduped,
        })

    update_source_history(payload["entities"], existing_log, existing_history)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
