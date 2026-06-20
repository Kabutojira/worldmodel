#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    "youtube_transcript": 0.75,
    "youtube_video": 0.55,
    "discord_public": 0.35,
    "discord_watchlist": 0.45,
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
    if any(token in title for token in ["investor", "sec", "ai", "supercharger", "tesla", "elon", "robotaxi", "battery"]):
        score += 0.1
    if source_type == "youtube_transcript":
        score += 0.05
    return min(score, 1.0)


def score_recency(candidate: dict[str, object]) -> float:
    if candidate.get("already_processed"):
        return 0.2
    if candidate.get("already_logged"):
        return 0.5
    return 0.9


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
            if item.get("already_processed"):
                item["skip_reason"] = "already used in update"
                skipped.append(item)
                continue
            if len(selected) >= args.limit_per_entity:
                item["skip_reason"] = f"limit_per_entity={args.limit_per_entity}"
                skipped.append(item)
                continue
            item["selection_reason"] = "top-ranked by quality/relevance/recency"
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
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
