#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

from worldmodel_common import DAILY_RUNS_HEADER, ENTITIES_DIR, ROOT, ensure_dir, iso_date, now_utc, read_csv, write_csv


REPORT_TEMPLATE = """# WorldModel Intelligence Report {run_date}

- Run ID: {run_id}
- Run date: {run_date}
- Entities processed: {entities_processed}
- Sources selected: {sources_selected_count}

## Executive view

{executive_view}

## Global thesis impact

{global_thesis_impact}

## Entity changes to review

{entity_changes}

## Connection changes to review

{connection_changes}

## New discoveries and weak signals

{new_discoveries}

## Mispricing / investment signals

{mispricing_signals}

## Source impact map

{source_impact_map}

## Open questions for investment work

{open_questions}

## Next research actions

{next_actions}

## Appendix: selected sources

{selected_sources}

## Appendix: skipped sources

{skipped_sources}

## Appendix: operational notes

{operational_notes}

## Appendix: modified files

{modified_files}
"""


def create_run_id() -> str:
    return f"worldmodel-{now_utc().replace(':', '').replace('-', '').lower()}"


def update_daily_runs(run_id: str, run_date: str, entities: list[dict[str, object]]) -> None:
    path = ROOT / "data" / "daily_runs.csv"
    rows = read_csv(path)
    finished_at = now_utc()
    entity_slugs = [str(entity.get("slug", "unknown")) for entity in entities]
    selected_count = sum(len(object_list(entity.get("selected"))) for entity in entities)
    row = {
        "run_id": run_id,
        "run_date": run_date,
        "started_at": finished_at,
        "finished_at": finished_at,
        "status": "completed",
        "entities_processed": ",".join(entity_slugs),
        "sources_selected": str(selected_count),
        "files_changed": "",
        "commit_sha": "",
        "notes": "Daily intelligence report generated; LLM synthesis should replace placeholders with thesis, relationship, and mispricing impact.",
    }
    replaced = False
    for idx, existing in enumerate(rows):
        if existing.get("run_id") == run_id:
            rows[idx] = {**existing, **row}
            replaced = True
            break
    if not replaced:
        rows.append(row)
    write_csv(path, rows, DAILY_RUNS_HEADER)


def git_modified_paths() -> list[str]:
    proc = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    paths = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        paths.append(path)
    return paths


def object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def bullet_list(items: list[str], empty_message: str) -> str:
    return "\n".join(items) if items else f"- {empty_message}"


def html_source_line(item: dict[str, object]) -> str:
    title = str(item.get("title", "Untitled"))
    url = str(item.get("url", ""))
    source_type = str(item.get("source_type", "unknown"))
    source_name = str(item.get("source_name", "unknown"))
    score = item.get("final_score")
    score_text = f", score {score:.3f}" if isinstance(score, (int, float)) else ""
    return f'- <a href="{url}">{title}</a> ({source_name}; {source_type}{score_text})'


def selected_items(entity: dict[str, object]) -> list[dict[str, object]]:
    return object_list(entity.get("selected"))


def summarize_selected(entity: dict[str, object]) -> str:
    selected = [html_source_line(item) for item in selected_items(entity)]
    return bullet_list(selected, "No selected sources.")


def summarize_skipped(entity: dict[str, object]) -> str:
    lines = []
    for item in object_list(entity.get("skipped")):
        title = str(item.get("title", "Untitled"))
        reason = str(item.get("skip_reason", "skipped"))
        url = str(item.get("url", ""))
        lines.append(f'- <a href="{url}">{title}</a> ({reason})')
    return bullet_list(lines, "None.")


def summarize_modified_files(report_path: Path, extra_paths: list[str]) -> str:
    modified = sorted(set(git_modified_paths()) | set(extra_paths))
    lines = []
    for path in modified:
        target = (ROOT / path).resolve()
        link = os.path.relpath(target, start=report_path.parent)
        lines.append(f'- [`{path}`]({Path(link).as_posix()})')
    return bullet_list(lines, "No modified files detected.")


def infer_source_themes(items: list[dict[str, object]]) -> Counter[str]:
    themes: Counter[str] = Counter()
    theme_keywords = {
        "AI infrastructure / compute": ["nvidia", "gpu", "ai", "datacenter", "data center", "compute", "semiconductor", "tsmc"],
        "Power / grid bottlenecks": ["electricity", "power", "grid", "energy", "nuclear", "gas", "transformer"],
        "Autonomy / robotics optionality": ["robotaxi", "fsd", "autonomy", "robot", "humanoid", "waymo"],
        "EV / battery supply chain": ["tesla", "ev", "battery", "lithium", "megapack", "charging"],
        "Platform strategy / distribution": ["google", "meta", "microsoft", "amazon", "apple", "openai", "anthropic"],
        "Macro / geopolitics": ["taiwan", "china", "tariff", "rates", "macro", "supply chain"],
        "Space / connectivity": ["spacex", "starlink", "satellite", "space", "launch"],
    }
    for item in items:
        haystack = f"{item.get('title', '')} {item.get('source_name', '')} {item.get('url', '')} {item.get('notes', '')}".lower()
        for theme, keywords in theme_keywords.items():
            if any(keyword in haystack for keyword in keywords):
                themes[theme] += 1
    return themes


def source_impact_lines(entity: dict[str, object]) -> list[str]:
    lines = []
    for item in selected_items(entity):
        title = str(item.get("title", "Untitled"))
        source_type = str(item.get("source_type", "unknown"))
        url = str(item.get("url", ""))
        themes = infer_source_themes([item])
        theme_text = ", ".join(themes) if themes else "needs classification"
        lines.append(
            f'- `{entity.get("slug", "unknown")}`: <a href="{url}">{title}</a> ({source_type}) — likely touches **{theme_text}**. Synthesis required: extract evidence, affected thesis, impacted entities, and investable signal.'
        )
    return lines


def content_context(entity: dict[str, object]) -> dict[str, str]:
    slug = str(entity.get("slug", "unknown"))
    selected = selected_items(entity)
    themes = infer_source_themes(selected)
    theme_summary = ", ".join(f"{theme} ({count})" for theme, count in themes.most_common()) or "no clear theme detected"
    source_types = Counter(str(item.get("source_type", "unknown")) for item in selected)
    source_type_summary = ", ".join(f"{kind}: {count}" for kind, count in source_types.most_common()) or "none"

    return {
        "executive_view": (
            f"- `{slug}` has {len(selected)} selected source(s). Dominant source mix: {source_type_summary}.\n"
            f"- Detected themes: {theme_summary}.\n"
            "- Replace this scaffold with a concise investment judgment after reading sources: what changed, what did not change, and what matters for capital allocation."
        ),
        "global_thesis_impact": (
            "- For each material source, state whether it strengthens, weakens, or leaves unchanged the global WorldModel thesis.\n"
            "- Focus on AI → data centers → power/grid → semiconductors/commodities, Tesla optionality, autonomy/robotics, and platform distribution.\n"
            "- Do not report infrastructure work here unless it changes research quality or source coverage."
        ),
        "entity_changes": (
            f"- `{slug}`: classify changes as bullish/base/bearish/no-change. Include evidence-backed updates to wiki, thesis, estimates, or financial report.\n"
            "- Mention new/paused entities only if a source changes their investment relevance."
        ),
        "connection_changes": (
            "- Identify source-backed changes to relationships: supplier, bottleneck, competitor, substitute, demand driver, regulation, or key-person link.\n"
            "- State the causal/financial mechanism and the direction of impact."
        ),
        "new_discoveries": (
            "- List genuinely new facts, weak signals, or contradictions found in sources.\n"
            "- Separate evidence from inference. Do not include repository plumbing changes."
        ),
        "mispricing_signals": (
            "- Look for gaps between likely fundamentals and market narrative: underpriced bottlenecks, overhyped optionality, delayed capex constraints, margin pressure, or consensus blind spots.\n"
            "- Mark each signal as evidence / inference / confidence / time horizon."
        ),
        "source_impact_map": bullet_list(source_impact_lines(entity), "No source impact map available."),
        "open_questions": (
            "- What source-backed fact would most change the current investment view?\n"
            "- Which linked entity should be updated next because this source changes its economics?\n"
            "- What metric or market price would confirm/disconfirm the signal?"
        ),
        "next_actions": (
            "- Read selected sources and update content files, not just logs.\n"
            "- Update thesis/relationships/estimates when evidence changes the view.\n"
            "- Convert recurring weak signals into tracked metrics or new entity relationships."
        ),
    }


def report_context(entity: dict[str, object], run_date: str, run_id: str, report_path: Path) -> dict[str, str]:
    slug = str(entity.get("slug", "unknown"))
    global_report = f"reports/daily/report_{run_date}.md"
    entity_report = f"entities/{slug}/daily_reports/report_{run_date}.md"
    ctx = content_context(entity)
    ctx.update({
        "run_id": run_id,
        "run_date": run_date,
        "entities_processed": slug,
        "sources_selected_count": str(len(selected_items(entity))),
        "selected_sources": summarize_selected(entity),
        "skipped_sources": summarize_skipped(entity),
        "modified_files": summarize_modified_files(report_path, [global_report, entity_report, "data/source_log.csv", f"entities/{slug}/source_log.csv", "data/entities.csv", "data/daily_runs.csv", "index.md"]),
        "operational_notes": "- Operational details are intentionally quarantined in this appendix. Promote only items that affect content quality, source coverage, or investment signal reliability.",
    })
    return ctx


def combine_global_context(entities: list[dict[str, object]], run_date: str, run_id: str, global_report_path: Path) -> dict[str, str]:
    all_selected = [item for entity in entities for item in selected_items(entity)]
    themes = infer_source_themes(all_selected)
    theme_summary = ", ".join(f"{theme} ({count})" for theme, count in themes.most_common()) or "no clear theme detected"
    source_types = Counter(str(item.get("source_type", "unknown")) for item in all_selected)
    source_type_summary = ", ".join(f"{kind}: {count}" for kind, count in source_types.most_common()) or "none"
    entities_by_sources = sorted(((str(e.get("slug", "unknown")), len(selected_items(e))) for e in entities), key=lambda x: (-x[1], x[0]))
    top_entities = ", ".join(f"`{slug}` ({count})" for slug, count in entities_by_sources[:15]) or "none"

    entity_blocks = [f"- `{slug}`: {count} selected source(s); synthesize thesis/entity/connection impact." for slug, count in entities_by_sources if count]
    source_lines = [line for entity in entities for line in source_impact_lines(entity)]
    selected_lines = []
    skipped_lines = []
    for entity in entities:
        slug = str(entity.get("slug", "unknown"))
        for item in selected_items(entity):
            selected_lines.append(f"- `{slug}` {html_source_line(item)[2:]}")
        for item in object_list(entity.get("skipped"))[:5]:
            title = str(item.get("title", "Untitled"))
            reason = str(item.get("skip_reason", "skipped"))
            url = str(item.get("url", ""))
            skipped_lines.append(f'- `{slug}` <a href="{url}">{title}</a> ({reason})')

    return {
        "run_id": run_id,
        "run_date": run_date,
        "entities_processed": ", ".join(str(entity.get("slug", "unknown")) for entity in entities) or "none",
        "sources_selected_count": str(len(all_selected)),
        "executive_view": (
            f"- Selected {len(all_selected)} source(s) across {len(entities)} entities.\n"
            f"- Highest-activity entities: {top_entities}.\n"
            f"- Source mix: {source_type_summary}.\n"
            f"- Detected themes: {theme_summary}.\n"
            "- The report must answer: what changed in the investable map, what connections matter more/less, and where market expectations may be wrong."
        ),
        "global_thesis_impact": (
            "- Synthesize source-backed impact on the global map, especially AI infrastructure, power/grid constraints, semiconductors, Tesla/autonomy/robotics, space/connectivity, and platform distribution.\n"
            "- Classify each impact: strengthens thesis / weakens thesis / adds uncertainty / no material change.\n"
            "- Avoid reporting implementation details unless they materially improve source coverage."
        ),
        "entity_changes": bullet_list(entity_blocks, "No entity changes to review."),
        "connection_changes": (
            "- Review whether selected sources alter causal chains: AI demand → GPU/HBM/TSMC/ASML; data centers → electricity/grid/transformers/copper/natural gas/nuclear; Tesla → battery/lithium/robotaxi/humanoids/xAI/Nvidia.\n"
            "- Add or revise relationships only with evidence URL, mechanism, and investment relevance."
        ),
        "new_discoveries": (
            "- Extract new facts or weak signals from selected sources.\n"
            "- Prioritize facts that update market size, margins, capex, capacity, regulation, adoption, or competitive positioning."
        ),
        "mispricing_signals": (
            "- Identify potential mispricing signals from the source set: consensus blind spots, underappreciated bottlenecks, overcapitalized narratives, or cross-entity second-order effects.\n"
            "- For each signal include evidence, inference, confidence, time horizon, and what would falsify it."
        ),
        "source_impact_map": bullet_list(source_lines, "No selected sources to map."),
        "open_questions": (
            "- Which thesis has the largest evidence gap?\n"
            "- Which entity relationship is most likely to be mispriced by public markets?\n"
            "- What metric/source should be tracked next to validate the signal?"
        ),
        "next_actions": (
            "- Read the highest-scoring sources and update content pages with investment-relevant synthesis.\n"
            "- Update relationships and estimates where evidence changes the causal model.\n"
            "- Add new tracked metrics for recurring bottleneck or mispricing signals."
        ),
        "selected_sources": bullet_list(selected_lines, "No selected sources."),
        "skipped_sources": bullet_list(skipped_lines, "None."),
        "operational_notes": "- Operational details moved to appendix by design. The main report should be content intelligence, not infrastructure changelog.",
        "modified_files": summarize_modified_files(global_report_path, [f"reports/daily/report_{run_date}.md", "data/source_log.csv", "data/entities.csv", "data/daily_runs.csv", "index.md"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WorldModel daily intelligence report scaffolds from ranked source output.")
    parser.add_argument("--selected", default=str(ROOT / ".worldmodel" / "selected.json"))
    parser.add_argument("--run-date", default=iso_date())
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    selected_path = Path(args.selected)
    data = json.loads(selected_path.read_text(encoding="utf-8"))
    run_id = args.run_id or create_run_id()
    run_date = args.run_date

    global_report_path = ROOT / "reports" / "daily" / f"report_{run_date}.md"
    ensure_dir(global_report_path.parent)

    entities = object_list(data.get("entities"))
    for entity in entities:
        slug = str(entity.get("slug", "unknown"))
        entity_report_path = ENTITIES_DIR / slug / "daily_reports" / f"report_{run_date}.md"
        ensure_dir(entity_report_path.parent)
        context = report_context(entity, run_date, run_id, entity_report_path)
        entity_report_path.write_text(REPORT_TEMPLATE.format(**context), encoding="utf-8")

    global_context = combine_global_context(entities, run_date, run_id, global_report_path)
    global_report_path.write_text(REPORT_TEMPLATE.format(**global_context), encoding="utf-8")
    update_daily_runs(run_id, run_date, entities)
    print(json.dumps({"global_report": str(global_report_path), "entities": len(entities), "run_id": run_id, "selected_sources": global_context["sources_selected_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
