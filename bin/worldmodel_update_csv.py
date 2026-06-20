#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worldmodel_common import DAILY_RUNS_HEADER, ENTITIES_DIR, ENTITIES_HEADER, ESTIMATES_HEADER, RELATIONSHIPS_HEADER, ROOT, SOURCE_LOG_HEADER, read_csv, validate_header, write_csv


def merge_estimates() -> list[dict[str, str]]:
    merged: dict[tuple[str, ...], dict[str, str]] = {}
    for path in sorted(ENTITIES_DIR.glob('*/estimates.csv')):
        validate_header(path, ESTIMATES_HEADER)
        for row in read_csv(path):
            key = tuple(row.get(field, '') for field in ["entity_slug", "business_line", "metric", "year", "actual_or_estimate"])
            merged[key] = row
    rows = list(merged.values())
    rows.sort(key=lambda r: (r.get("entity_slug", ""), r.get("business_line", ""), r.get("metric", ""), r.get("year", ""), r.get("actual_or_estimate", "")))
    return rows


def validate_estimate_rows(rows: list[dict[str, str]]) -> None:
    for row in rows:
        if not row.get("entity_slug"):
            raise ValueError("estimate row missing entity_slug")
        for field in ["bearish_forecast", "normal_forecast", "bullish_forecast", "bearish_thesis", "normal_thesis", "bullish_thesis"]:
            if field not in row:
                raise ValueError(f"estimate row missing field {field}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and merge WorldModel CSV files.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--merge-all", action="store_true")
    args = parser.parse_args()

    validate_header(ROOT / 'data' / 'entities.csv', ENTITIES_HEADER)
    validate_header(ROOT / 'data' / 'relationships.csv', RELATIONSHIPS_HEADER)
    validate_header(ROOT / 'data' / 'estimates.csv', ESTIMATES_HEADER)
    validate_header(ROOT / 'data' / 'source_log.csv', SOURCE_LOG_HEADER)
    validate_header(ROOT / 'data' / 'daily_runs.csv', DAILY_RUNS_HEADER)

    if args.merge_all:
        rows = merge_estimates()
        validate_estimate_rows(rows)
        write_csv(ROOT / 'data' / 'estimates.csv', rows, ESTIMATES_HEADER)
        print(f"merged {len(rows)} estimate rows")
    elif args.validate:
        print("validation ok")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
