#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worldmodel_common import ENTITIES_DIR, ENTITIES_HEADER, ESTIMATES_HEADER, SOURCE_LOG_HEADER, ROOT, WIKI_PAGES, ensure_dir, load_template, read_csv, render_template, slugify, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a new WorldModel entity from templates.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--type", required=True)
    parser.add_argument("--ticker", default="")
    parser.add_argument("--priority", required=True)
    args = parser.parse_args()

    slug = args.slug or slugify(args.name)
    entity_dir = ENTITIES_DIR / slug
    if entity_dir.exists():
        raise SystemExit(f"entity already exists: {slug}")

    entities_path = ROOT / "data" / "entities.csv"
    rows = read_csv(entities_path)
    if any(row.get("slug") == slug for row in rows):
        raise SystemExit(f"slug already present in data/entities.csv: {slug}")

    ensure_dir(entity_dir / "wiki")
    ensure_dir(entity_dir / "daily_reports")

    replacements = {
        "entity_name": args.name,
        "slug": slug,
        "type": args.type,
        "status": "paused",
        "priority": str(args.priority),
        "ticker": args.ticker,
        "connected_entity": "example-connected-entity",
    }

    for page in WIKI_PAGES:
        target = entity_dir / "wiki" / page
        if page == "index.md":
            target.write_text(render_template(load_template("entity.md"), replacements), encoding="utf-8")
        else:
            target.write_text(f"# {args.name} {page.replace('.md', '').title()}\n", encoding="utf-8")

    (entity_dir / "thesis.md").write_text(render_template(load_template("thesis.md"), replacements), encoding="utf-8")
    (entity_dir / "financial_report.md").write_text(render_template(load_template("financial_report.md"), replacements), encoding="utf-8")
    (entity_dir / "estimates.csv").write_text(",".join(ESTIMATES_HEADER) + "\n", encoding='utf-8')
    (entity_dir / "source_log.csv").write_text(",".join(SOURCE_LOG_HEADER) + "\n", encoding='utf-8')

    rows.append({
        "entity_id": f"entity_{slug}",
        "slug": slug,
        "name": args.name,
        "type": args.type,
        "status": "paused",
        "priority": str(args.priority),
        "ticker": args.ticker,
    })
    write_csv(entities_path, rows, ENTITIES_HEADER)
    print(f"initialized {slug} at {entity_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
