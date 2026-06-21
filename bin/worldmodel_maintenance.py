#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worldmodel_common import (
    DAILY_RUNS_HEADER,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check WorldModel repository maintenance invariants.")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    validate_header(ROOT / "data" / "entities.csv", ENTITIES_HEADER)
    validate_header(ROOT / "data" / "relationships.csv", RELATIONSHIPS_HEADER)
    validate_header(ROOT / "data" / "estimates.csv", ESTIMATES_HEADER)
    validate_header(ROOT / "data" / "source_log.csv", SOURCE_LOG_HEADER)
    validate_header(ROOT / "data" / "daily_runs.csv", DAILY_RUNS_HEADER)

    findings = []
    findings.extend(find_missing_entity_files())
    findings.extend(find_broken_links())
    findings.extend(find_relationship_gaps())
    if not (ROOT / "AGENTS.md").exists() or not (ROOT / "PLAN.md").exists():
        findings.append("AGENTS.md or PLAN.md missing")
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
