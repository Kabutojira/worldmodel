#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from worldmodel_common import DAILY_RUNS_HEADER, ENTITIES_DIR, ROOT, ensure_dir, iso_date, now_utc, read_csv, write_csv


REPORT_TEMPLATE = """# Daily Report {run_date}

- Run ID: {run_id}
- Run date: {run_date}
- Entities processed: {entities_processed}

## Selected sources

{selected_sources}

## Skipped sources

{skipped_sources}

## Modified files

{modified_files}

## Facts added

{facts_added}

## Thesis changes

{thesis_changes}

## CSV updates

{csv_updates}

## Relationship changes

{relationship_changes}

## Mispricing / tendency signals

{mispricing_signals}

## Issues / inefficiencies

{issues}

## Open questions

{open_questions}

## Next actions

{next_actions}
"""


def latest_run_id() -> str:
    rows = read_csv(ROOT / "data" / "daily_runs.csv")
    if not rows:
        return f"worldmodel-{now_utc().replace(':', '').replace('-', '').lower()}"
    return rows[-1].get("run_id") or f"worldmodel-{now_utc().replace(':', '').replace('-', '').lower()}"


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
        "notes": "Deterministic daily pipeline completed through report generation/render preparation.",
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


def html_source_line(item: dict[str, object]) -> str:
    title = str(item.get("title", "Untitled"))
    url = str(item.get("url", ""))
    source_type = str(item.get("source_type", "unknown"))
    discovery_state = str(item.get("discovery_state", "unknown"))
    processing_state = str(item.get("processing_state", "unknown"))
    score = item.get("final_score")
    score_text = f", score {score:.3f}" if isinstance(score, (int, float)) else ""
    state_text = f", discovery={discovery_state}, processing={processing_state}"
    return f'- <a href="{url}">{title}</a> ({source_type}{score_text}{state_text})'


def bullet_list(items: list[str], empty_message: str) -> str:
    return "\n".join(items) if items else f"- {empty_message}"


def object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def summarize_selected(entity: dict[str, object]) -> str:
    selected = [html_source_line(item) for item in object_list(entity.get("selected"))]
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


def summarize_csv_updates(entity: dict[str, object]) -> str:
    selected = object_list(entity.get("selected"))
    new_candidates = sum(1 for item in selected if item.get("discovery_state") == "new_candidate")
    logged_unprocessed = sum(1 for item in selected if item.get("processing_state") == "logged_unprocessed")
    lines = [
        f'- Selected {len(selected)} sources for `{entity.get("slug", "unknown")}`.',
        f'- Discovery state split: {new_candidates} new candidate(s) and {len(selected) - new_candidates} already-logged candidate(s).',
        f'- Processing state split: {logged_unprocessed} logged-but-unsynthesized candidate(s) remain visible separately from fully synthesized items.',
        f'- `data/entities.csv` should reflect refreshed retrieval metadata for `{entity.get("slug", "unknown")}`.',
        f'- `data/source_log.csv` and `entities/{entity.get("slug", "unknown")}/source_log.csv` should be updated during the daily run when sources are processed.',
    ]
    return "\n".join(lines)


def summarize_issues(entity: dict[str, object], transcript_manifest: dict[str, object] | None) -> str:
    issues: list[str] = []
    selected = object_list(entity.get("selected"))
    fresh = [item for item in selected if item.get("discovery_state") == "new_candidate"]
    logged_unprocessed = [item for item in selected if item.get("processing_state") == "logged_unprocessed"]
    if not fresh:
        issues.append("- Retrieval surfaced no fresh candidate sources; the run is re-ranking already-logged material.")
    if logged_unprocessed:
        issues.append(f"- {len(logged_unprocessed)} selected source(s) are logged but not yet synthesized; the new state split makes that backlog explicit.")
    if len(selected) <= 5:
        issues.append("- Candidate diversity is still low; retrieval remains too dependent on static seed URLs.")
    transcript_failures = []
    if transcript_manifest:
        for video in object_list(transcript_manifest.get("videos")):
            if not video.get("transcript_available"):
                transcript_failures.append(str(video.get("title", "unknown video")))
    if transcript_failures:
        issues.append(f"- YouTube transcript fetch is blocked or unavailable for {len(transcript_failures)} videos, so channel ingestion falls back to metadata only.")
    if any(item.get("source_type") == "youtube_video" and not item.get("transcript_available") for item in selected):
        issues.append("- Selected YouTube items do not have transcript text attached, which reduces their synthesis value.")
    if any(item.get("source_type") == "seeking_alpha" for item in selected):
        issues.append("- Seeking Alpha support is currently endpoint-based; it does not yet discover newly published article URLs automatically.")
    return bullet_list(issues, "No major issues detected by deterministic checks.")


def report_context(entity: dict[str, object], run_date: str, run_id: str, transcript_manifest: dict[str, object] | None, report_path: Path) -> dict[str, str]:
    slug = str(entity.get("slug", "unknown"))
    global_report = f"reports/daily/report_{run_date}.md"
    entity_report = f"entities/{slug}/daily_reports/report_{run_date}.md"
    return {
        "run_id": run_id,
        "run_date": run_date,
        "entities_processed": slug,
        "selected_sources": summarize_selected(entity),
        "skipped_sources": summarize_skipped(entity),
        "modified_files": summarize_modified_files(report_path, [global_report, entity_report, "data/source_log.csv", f"entities/{slug}/source_log.csv", "data/entities.csv", "data/daily_runs.csv", "index.md"]),
        "facts_added": "- No deterministic fact extraction is performed here. Use the selected source set for LLM-backed evidence extraction.",
        "thesis_changes": "- None in this deterministic stage. Update after source reading and thesis synthesis.",
        "csv_updates": summarize_csv_updates(entity),
        "relationship_changes": "- None in this deterministic stage.",
        "mispricing_signals": "- *Evidence:* Primary sources and ranked external research are now assembled for review.\n- *Inference:* Mispricing detection still depends on the subsequent synthesis step; this script only improves run visibility and issue reporting.",
        "issues": summarize_issues(entity, transcript_manifest),
        "open_questions": "- Which selected sources should become the next source-backed baseline for thesis and estimates?\n- Which additional source adapters would most improve source diversity for this entity?\n- Should the workflow persist `processing_state` history in a dedicated deterministic artifact beyond the ranked JSON output?",
        "next_actions": "- Read and synthesize the selected sources.\n- Update wiki, thesis, estimates, and relationships from source-backed evidence.\n- Re-run maintenance, then commit and push the resulting repository changes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic WorldModel daily report skeletons from ranked source output.")
    parser.add_argument("--selected", default=str(ROOT / ".worldmodel" / "selected.json"))
    parser.add_argument("--run-date", default=iso_date())
    parser.add_argument("--run-id", default="")
    parser.add_argument("--transcript-manifest", default=str(ROOT / ".worldmodel" / "youtube_transcripts_index.json"))
    args = parser.parse_args()

    selected_path = Path(args.selected)
    data = json.loads(selected_path.read_text(encoding="utf-8"))
    run_id = args.run_id or create_run_id()
    run_date = args.run_date
    transcript_manifest = None
    transcript_path = Path(args.transcript_manifest)
    if transcript_path.exists():
        transcript_manifest = json.loads(transcript_path.read_text(encoding="utf-8"))

    global_report_path = ROOT / "reports" / "daily" / f"report_{run_date}.md"
    ensure_dir(global_report_path.parent)

    entity_blocks = []
    first_entity_context = None
    entities = object_list(data.get("entities"))
    for entity in entities:
        entity_report_path = ENTITIES_DIR / str(entity.get("slug", "unknown")) / "daily_reports" / f"report_{run_date}.md"
        context = report_context(entity, run_date, run_id, transcript_manifest, entity_report_path)
        if first_entity_context is None:
            first_entity_context = context
        ensure_dir(entity_report_path.parent)
        entity_report_path.write_text(REPORT_TEMPLATE.format(**context), encoding="utf-8")
        entity_blocks.append(f"- {entity.get('slug', 'unknown')}: {len(object_list(entity.get('selected')))} selected / {len(object_list(entity.get('skipped')))} skipped")

    if first_entity_context is None:
        first_entity_context = {
            "run_id": run_id,
            "run_date": run_date,
            "entities_processed": "none",
            "selected_sources": "- No entities were present in the selected source file.",
            "skipped_sources": "- None.",
            "modified_files": summarize_modified_files(global_report_path, [f"reports/daily/report_{run_date}.md"]),
            "facts_added": "- None.",
            "thesis_changes": "- None.",
            "csv_updates": "- None.",
            "relationship_changes": "- None.",
            "mispricing_signals": "- None.",
            "issues": "- No entities found in ranked source output.",
            "open_questions": "- Why was the selected source file empty?",
            "next_actions": "- Fix retrieval or ranking before the next run.",
        }
    global_context = dict(first_entity_context)
    global_context["entities_processed"] = ", ".join(str(entity.get("slug", "unknown")) for entity in entities) or "none"
    global_context["modified_files"] = summarize_modified_files(global_report_path, [f"reports/daily/report_{run_date}.md", "data/source_log.csv", "data/entities.csv", "data/daily_runs.csv", "index.md"])
    global_context["csv_updates"] = bullet_list(entity_blocks, "No entity summary available.") + "\n- Review `data/daily_runs.csv` and source logs for the finalized run record."
    global_report_path.write_text(REPORT_TEMPLATE.format(**global_context), encoding="utf-8")
    update_daily_runs(run_id, run_date, entities)
    print(json.dumps({"global_report": str(global_report_path), "entities": len(entities), "run_id": run_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
