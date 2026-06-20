#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ENTITIES_DIR = ROOT / "entities"
DOCS_DIR = ROOT / "docs"

ENTITIES_HEADER = [
    "entity_id","slug","name","type","status","priority","ticker","exchange","currency",
    "geography","sector","industry","business_lines","description","search_keywords",
    "connected_entities","last_retrieval_at","last_report_date","last_source_count","confidence","owner_notes",
]
RELATIONSHIPS_HEADER = [
    "source_slug","target_slug","relationship_type","direction","importance","mechanism",
    "why_connected","evidence_url","last_reviewed_at","confidence",
]
ESTIMATES_HEADER = [
    "entity_slug","entity_name","type","business_line","metric","unit","currency","actual_or_estimate",
    "year","base_value","bearish_forecast","normal_forecast","bullish_forecast","bearish_thesis",
    "normal_thesis","bullish_thesis","source_url","source_date","updated_at","confidence","notes",
]
SOURCE_LOG_HEADER = [
    "source_id","entity_slug","title","source_name","source_type","url","author","published_at","retrieved_at",
    "quality_score","recency_score","relevance_score","used_in_update","summary_path","hash","notes",
]
DAILY_RUNS_HEADER = [
    "run_id","run_date","started_at","finished_at","status","entities_processed","sources_selected",
    "files_changed","commit_sha","notes",
]
WIKI_PAGES = ["index.md", "business.md", "market.md", "financials.md", "technology.md", "people.md", "risks.md", "sources.md"]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_date() -> str:
    return dt.date.today().isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def write_csv(path: Path, rows: list[dict[str, str]], header: list[str]) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})
    tmp.replace(path)


def validate_header(path: Path, expected: list[str]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        actual = next(reader, None)
    if actual != expected:
        raise ValueError(f"header mismatch in {path}: expected {expected}, got {actual}")


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    split = urlsplit(url.strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if not k.lower().startswith("utm_")))
    clean_path = re.sub(r"/{2,}", "/", split.path or "/")
    scheme = split.scheme.lower() or "https"
    netloc = split.netloc.lower()
    return urlunsplit((scheme, netloc, clean_path.rstrip("/") or "/", query, ""))


def stable_hash(*parts: str) -> str:
    joined = "||".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_index_entities(index_path: Path | None = None) -> list[dict[str, object]]:
    path = index_path or ROOT / "index.md"
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n## ", text)
    entities: list[dict[str, object]] = []
    for raw in blocks[1:]:
        block = "## " + raw
        header = raw.splitlines()[0].strip()
        entity: dict[str, object] = {"name": header, "search_keywords": [], "source_priority": [], "connected_entities": []}
        current = None
        for line in block.splitlines()[1:]:
            stripped = line.strip()
            if stripped.startswith("- Slug:"):
                entity["slug"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Type:"):
                entity["type"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Status:"):
                entity["status"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Priority:"):
                entity["priority"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Last retrieval:"):
                entity["last_retrieval"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Last report:"):
                entity["last_report"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- Notes:"):
                entity["notes"] = stripped.split(":", 1)[1].strip()
            elif stripped == "- Search keywords:":
                current = "search_keywords"
            elif stripped == "- Source priority:":
                current = "source_priority"
            elif stripped == "- Connected entities:":
                current = "connected_entities"
            elif stripped.startswith("- ") and current in {"search_keywords", "source_priority"}:
                entity[current].append(stripped[2:].strip().strip('"'))
            elif stripped.startswith("- ") and current == "connected_entities":
                item = stripped[2:].strip()
                if ":" in item:
                    label, why = item.split(":", 1)
                    entity[current].append({"name": label.strip(), "why": why.strip()})
        entities.append(entity)
    return entities


def render_template(text: str, mapping: dict[str, str]) -> str:
    rendered = text
    for key, value in mapping.items():
        rendered = rendered.replace("{{ " + key + " }}", value)
    return rendered


def load_template(name: str) -> str:
    return (ROOT / "templates" / name).read_text(encoding="utf-8")


def markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
