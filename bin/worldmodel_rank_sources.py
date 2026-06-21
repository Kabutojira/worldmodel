#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from worldmodel_common import ROOT, SOURCE_HISTORY_HEADER, now_utc, read_csv, validate_header, write_csv

SOURCE_QUALITY = {
    "investor_relations": 1.0,
    "filing_index": 1.0,
    "sec_companyfacts": 1.0,
    "official_site": 0.9,
    "earnings_transcript": 0.9,
    "investor_presentation": 0.95,
    "trade_publication": 0.8,
    "deep_dive": 0.7,
    "seeking_alpha": 0.7,
    "substack_post": 0.75,
    "substack_feed_error": 0.1,
    "youtube_transcript": 0.75,
    "youtube_video": 0.55,
    "technical_x": 0.45,
    "data_x": 0.45,
    "news": 0.5,
    "x_post": 0.3,
}


def score_relevance(candidate: dict[str, object], entity_name: str) -> float:
    title = str(candidate.get("title", "")).lower()
    url = str(candidate.get("url", "")).lower()
    source_type = str(candidate.get("source_type", ""))
    score = 0.6
    if entity_name.lower() in title:
        score += 0.2
    if entity_name.lower() in url:
        score += 0.1
    if any(token in title for token in ["investor", "sec", "ai", "supercharger", "tesla", "elon", "robotaxi", "battery", "datacenter", "power", "grid", "semiconductor"]):
        score += 0.1
    if source_type == "youtube_transcript":
        score += 0.05
    return min(score, 1.0)


def score_recency(candidate: dict[str, object]) -> float:
    processing = str(candidate.get("processing_state", ""))
    discovery = str(candidate.get("discovery_state", ""))
    if processing == "fully_synthesized" or candidate.get("already_processed"):
        return 0.2
    if processing == "logged_unprocessed":
        return 0.6
    if discovery == "already_logged" or candidate.get("already_logged"):
        return 0.5
    return 0.9


def load_source_history() -> dict[str, dict[str, str]]:
    path = ROOT / "data" / "source_history.csv"
    validate_header(path, SOURCE_HISTORY_HEADER)
    return {str(row.get("history_key", "")).strip(): row for row in read_csv(path) if row.get("history_key")}


def to_int(value: object) -> int:
    try:
        return int(str(value).strip() or "0")
    except Exception:
        return 0


def update_history(history_rows: dict[str, dict[str, str]], ranked_entities: list[dict[str, object]]) -> None:
    now = now_utc()
    selected_keys = set()
    for entity in ranked_entities:
        raw_selected = entity.get("selected", [])
        if not isinstance(raw_selected, list):
            continue
        for item in raw_selected:
            if not isinstance(item, dict):
                continue
            key = str(item.get("source_history_key", "")).strip()
            if not key:
                continue
            selected_keys.add(key)
            row = dict(history_rows.get(key, {}))
            row["times_selected"] = str(to_int(row.get("times_selected")) + 1)
            row["last_selected_at"] = now
            if str(row.get("current_state", "")).strip() != "fully_synthesized":
                row["current_state"] = "selected_for_review"
            history_rows[key] = row
    for key, row in history_rows.items():
        if key in selected_keys:
            continue
        if str(row.get("current_state", "")).strip() == "selected_for_review":
            row["current_state"] = "logged_unprocessed"
    ordered = sorted(history_rows.values(), key=lambda row: (row.get("entity_slug", ""), row.get("url", "")))
    write_csv(ROOT / "data" / "source_history.csv", ordered, SOURCE_HISTORY_HEADER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank WorldModel candidate sources.")
    parser.add_argument("--in", dest="input_path", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit-per-entity", type=int, default=10)
    args = parser.parse_args()

    payload = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
    ranked = {"generated_at": payload.get("generated_at"), "entities": []}
    for entity in payload.get("entities", []):
        scored = []
        for candidate in entity.get("candidates", []):
            quality = SOURCE_QUALITY.get(candidate.get("source_type"), 0.5)
            relevance = score_relevance(candidate, entity.get("name", ""))
            recency = score_recency(candidate)
            final = quality * 0.45 + relevance * 0.35 + recency * 0.20
            record = dict(candidate)
            record.update({
                "quality_score": round(quality, 3),
                "relevance_score": round(relevance, 3),
                "recency_score": round(recency, 3),
                "final_score": round(final, 3),
            })
            scored.append(record)
        scored.sort(key=lambda row: (-row["final_score"], row["url"]))
        selected, skipped = [], []
        seen_hashes = set()
        for item in scored:
            if item["hash"] in seen_hashes:
                item["skip_reason"] = "duplicate hash"
                skipped.append(item)
                continue
            seen_hashes.add(item["hash"])
            if item.get("processing_state") == "fully_synthesized" or item.get("already_processed"):
                item["skip_reason"] = "already used in update"
                skipped.append(item)
                continue
            if len(selected) >= args.limit_per_entity:
                item["skip_reason"] = f"limit_per_entity={args.limit_per_entity}"
                skipped.append(item)
                continue
            item["selection_reason"] = (
                f"top-ranked by quality/relevance/recency; "
                f"discovery_state={item.get('discovery_state', 'unknown')}; "
                f"processing_state={item.get('processing_state', 'unknown')}"
            )
            selected.append(item)
        ranked["entities"].append({
            "slug": entity.get("slug"),
            "name": entity.get("name"),
            "selected": selected,
            "skipped": skipped,
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ranked, indent=2, sort_keys=True), encoding="utf-8")
    update_history(load_source_history(), ranked["entities"])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
