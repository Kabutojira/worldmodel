#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from urllib.parse import urlparse

from worldmodel_common import (
    DAILY_RUNS_HEADER,
    SOURCE_HISTORY_HEADER,
    SOURCE_REGISTRY_HEADER,
    SUBSTACK_WATCHLIST_HEADER,
    ENTITIES_DIR,
    ENTITIES_HEADER,
    ESTIMATES_HEADER,
    RELATIONSHIPS_HEADER,
    ROOT,
    SITE_CONTENT_DIR,
    SITE_DIR,
    SOURCE_LOG_HEADER,
    WIKI_PAGES,
    markdown_links,
    parse_index_entities,
    read_csv,
    validate_header,
)


def find_missing_entity_files() -> list[str]:
    findings = []
    for entity in parse_index_entities():
        slug = str(entity.get("slug", ""))
        base = ENTITIES_DIR / slug
        if not base.exists():
            findings.append(f"missing entity directory: {base}")
            continue
        for page in WIKI_PAGES:
            target = base / "wiki" / page
            if not target.exists():
                findings.append(f"missing wiki page: {target}")
        for file_name in ["thesis.md", "financial_report.md", "estimates.csv", "source_log.csv", "daily_reports"]:
            target = base / file_name
            if not target.exists():
                findings.append(f"missing entity file: {target}")
    return findings


def find_broken_links() -> list[str]:
    findings = []
    ignored = {SITE_DIR, ROOT / "docs"}
    for path in ROOT.rglob("*.md"):
        if any(path.is_relative_to(base) for base in ignored if base.exists()):
            continue
        for link in markdown_links(path.read_text(encoding="utf-8")):
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (path.parent / link).resolve()
            if not target.exists():
                findings.append(f"broken link in {path}: {link}")
    return findings


def find_relationship_gaps() -> list[str]:
    findings = []
    for row in read_csv(ROOT / "data" / "relationships.csv"):
        if not row.get("why_connected"):
            findings.append(f"relationship missing why_connected: {row.get('source_slug')}->{row.get('target_slug')}")
        if not row.get("mechanism"):
            findings.append(f"relationship missing mechanism: {row.get('source_slug')}->{row.get('target_slug')}")
    return findings


def find_substack_watchlist_gaps() -> list[str]:
    findings = []
    watchlist_path = ROOT / "data" / "substack_watchlist.csv"
    if not watchlist_path.exists():
        findings.append(f"missing Substack watchlist config: {watchlist_path}")
        return findings

    validate_header(watchlist_path, SUBSTACK_WATCHLIST_HEADER)
    stale_cutoff = dt.date.today() - dt.timedelta(days=30)
    for row in read_csv(watchlist_path):
        publication = str(row.get("publication", "")).strip()
        feed_url = str(row.get("feed_url", "")).strip()
        status = str(row.get("status", "active")).strip().lower()
        last_checked = str(row.get("last_checked_at", "")).strip()
        keywords = [part.strip() for part in str(row.get("keywords", "")).split(";") if part.strip()]
        row_label = publication or feed_url or "<blank row>"

        if not publication:
            findings.append(f"Substack watchlist entry missing publication: {row_label}")
        parsed = urlparse(feed_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            findings.append(f"Substack watchlist entry has malformed feed_url: {row_label}")
        if not keywords:
            findings.append(f"Substack watchlist entry missing keywords: {row_label}")
        if status not in {"active", "paused", "archived"}:
            findings.append(f"Substack watchlist entry has invalid status '{status}': {row_label}")
        if status == "active":
            if not last_checked:
                findings.append(f"Substack watchlist entry missing last_checked_at: {row_label}")
            else:
                try:
                    checked_date = dt.date.fromisoformat(last_checked)
                except ValueError:
                    findings.append(f"Substack watchlist entry has invalid last_checked_at '{last_checked}': {row_label}")
                else:
                    if checked_date < stale_cutoff:
                        findings.append(f"Substack watchlist entry is stale (>30d): {row_label}")
    return findings


def find_source_registry_gaps() -> list[str]:
    findings = []
    path = ROOT / "data" / "source_registry.csv"
    if not path.exists():
        findings.append(f"missing source registry: {path}")
        return findings
    validate_header(path, SOURCE_REGISTRY_HEADER)
    allowed_platforms = {"youtube", "substack", "x", "web", "website", "filing", "investor_relations", "podcast"}
    allowed_priorities = {"P0", "P1", "P2", "P3"}
    allowed_frequencies = {"daily", "weekly", "monthly", "quarterly", "ad_hoc", "manual"}
    seen_ids = set()
    for row in read_csv(path):
        source_id = str(row.get("source_id", "")).strip()
        platform = str(row.get("platform", "")).strip().lower()
        name = str(row.get("name", "")).strip()
        url = str(row.get("url", "")).strip()
        priority = str(row.get("priority", "")).strip().upper()
        entities = [part.strip() for part in str(row.get("entities", "")).split(";") if part.strip()]
        frequency = str(row.get("retrieval_frequency", "")).strip().lower()
        label = source_id or name or url or "<blank row>"
        if not source_id:
            findings.append(f"source registry entry missing source_id: {label}")
        elif source_id in seen_ids:
            findings.append(f"source registry has duplicate source_id: {source_id}")
        seen_ids.add(source_id)
        if platform not in allowed_platforms:
            findings.append(f"source registry entry has invalid platform '{platform}': {label}")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            findings.append(f"source registry entry has malformed url: {label}")
        if priority not in allowed_priorities:
            findings.append(f"source registry entry has invalid priority '{priority}': {label}")
        if not entities:
            findings.append(f"source registry entry missing entities: {label}")
        if frequency not in allowed_frequencies:
            findings.append(f"source registry entry has invalid retrieval_frequency '{frequency}': {label}")
    return findings


def find_source_history_gaps() -> list[str]:
    findings = []
    path = ROOT / "data" / "source_history.csv"
    if not path.exists():
        findings.append(f"missing source history: {path}")
        return findings
    validate_header(path, SOURCE_HISTORY_HEADER)
    seen_keys = set()
    for row in read_csv(path):
        key = str(row.get("history_key", "")).strip()
        url = str(row.get("url", "")).strip()
        if not key:
            findings.append("source history row missing history_key")
            continue
        if key in seen_keys:
            findings.append(f"duplicate source history key: {key}")
        seen_keys.add(key)
        if not url:
            findings.append(f"source history row missing url: {key}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check WorldModel repository maintenance invariants.")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    validate_header(ROOT / "data" / "entities.csv", ENTITIES_HEADER)
    validate_header(ROOT / "data" / "relationships.csv", RELATIONSHIPS_HEADER)
    validate_header(ROOT / "data" / "estimates.csv", ESTIMATES_HEADER)
    validate_header(ROOT / "data" / "source_log.csv", SOURCE_LOG_HEADER)
    validate_header(ROOT / "data" / "daily_runs.csv", DAILY_RUNS_HEADER)
    validate_header(ROOT / "data" / "source_registry.csv", SOURCE_REGISTRY_HEADER)
    validate_header(ROOT / "data" / "source_history.csv", SOURCE_HISTORY_HEADER)

    findings = []
    findings.extend(find_missing_entity_files())
    findings.extend(find_broken_links())
    findings.extend(find_relationship_gaps())
    findings.extend(find_substack_watchlist_gaps())
    findings.extend(find_source_registry_gaps())
    findings.extend(find_source_history_gaps())
    if not (ROOT / "AGENTS.md").exists() or not (ROOT / "PLAN.md").exists():
        findings.append("AGENTS.md or PLAN.md missing")
    if not (ROOT / "README.md").exists():
        findings.append("README.md missing")
    if not SITE_DIR.exists():
        findings.append("site/ missing; add Quartz project files")
    if not SITE_CONTENT_DIR.exists():
        findings.append("site/content missing; run render script")
    for required in [
        SITE_DIR / "package.json",
        SITE_DIR / "quartz.config.yaml",
        SITE_DIR / "quartz.layout.ts",
        ROOT / ".github" / "workflows" / "pages.yml",
        ROOT / "SITE.md",
    ]:
        if not required.exists():
            findings.append(f"missing site build file: {required}")
    print("maintenance findings:")
    if findings:
        for finding in findings:
            print(f"- {finding}")
        return 1 if args.strict else 0
    print("- none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
