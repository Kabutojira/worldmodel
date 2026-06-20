#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from worldmodel_common import ROOT, canonicalize_url, iso_date, now_utc, parse_index_entities, read_csv, stable_hash


def build_seed_candidates(entity: dict[str, object]) -> list[dict[str, object]]:
    slug = str(entity["slug"])
    name = str(entity["name"])
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
    return seeds


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
    payload = {"generated_at": now_utc(), "run_date": iso_date(), "entities": []}
    for entity in selected_entities:
        slug = str(entity["slug"])
        candidates = []
        for seed in build_seed_candidates(entity):
            url = canonicalize_url(str(seed["url"]))
            candidates.append({
                "entity_slug": slug,
                "entity_name": entity["name"],
                "title": seed["title"],
                "source_name": seed["source_name"],
                "source_type": seed["source_type"],
                "url": url,
                "published_at": "",
                "retrieved_at": now_utc(),
                "hash": stable_hash(slug, url, seed["title"]),
                "already_logged": url in existing,
                "search_keywords": entity.get("search_keywords", []),
            })
        payload["entities"].append({
            "slug": slug,
            "name": entity["name"],
            "last_report": entity.get("last_report", ""),
            "last_retrieval": entity.get("last_retrieval", ""),
            "candidates": candidates,
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
