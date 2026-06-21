#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from worldmodel_common import (
    DATA_DIR,
    ENTITIES_DIR,
    ENTITIES_HEADER,
    ESTIMATES_HEADER,
    RELATIONSHIPS_HEADER,
    ROOT,
    SITE_CONTENT_DIR,
    SITE_DIR,
    SOURCE_LOG_HEADER,
    WIKI_PAGES,
    canonicalize_url,
    ensure_dir,
    markdown_links,
    now_utc,
    parse_index_entities,
    read_csv,
    slugify,
    validate_header,
)

REQUIRED_ENTITY_FILES = ["thesis.md", "financial_report.md", "estimates.csv", "source_log.csv"]
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ROOT_MARKDOWN_COPIES = ["AGENTS.md", "PLAN.md", "SITE.md"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Quartz content for the WorldModel site.")
    parser.add_argument("--clean", action="store_true", help="Remove and recreate the generated content directory before rendering.")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the generated content directory before rendering.")
    parser.add_argument("--strict", action="store_true", help="Fail loudly on missing required inputs or empty graph/content output.")
    parser.add_argument("--content-dir", default=str(SITE_CONTENT_DIR), help="Quartz content output directory.")
    parser.add_argument("--graph-json", default=None, help="Path for generated graph metadata JSON.")
    return parser.parse_args()


def fail(message: str, strict: bool) -> None:
    if strict:
        raise SystemExit(message)


def verify_repo_inputs(strict: bool) -> None:
    if not (ROOT / "index.md").exists():
        fail("missing required file: index.md", strict)
    if not ENTITIES_DIR.exists():
        fail("missing required directory: entities/", strict)
    validate_header(DATA_DIR / "entities.csv", ENTITIES_HEADER)
    validate_header(DATA_DIR / "relationships.csv", RELATIONSHIPS_HEADER)
    validate_header(DATA_DIR / "estimates.csv", ESTIMATES_HEADER)
    validate_header(DATA_DIR / "source_log.csv", SOURCE_LOG_HEADER)


def load_entities() -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, object]], dict[str, str]]:
    entity_rows = read_csv(DATA_DIR / "entities.csv")
    entities_by_slug = {row["slug"]: row for row in entity_rows if row.get("slug")}
    index_entities = parse_index_entities()
    index_by_slug = {str(item.get("slug", "")): item for item in index_entities if item.get("slug")}
    name_to_slug = {}
    for row in entity_rows:
        slug = row.get("slug", "")
        name = row.get("name", "")
        if slug:
            name_to_slug[name.lower()] = slug
            name_to_slug[slug.lower()] = slug
            entity_id = row.get("entity_id", "")
            if entity_id:
                name_to_slug[entity_id.lower()] = slug
    for item in index_entities:
        slug = str(item.get("slug", ""))
        name = str(item.get("name", ""))
        if slug:
            name_to_slug[name.lower()] = slug
            name_to_slug[slug.lower()] = slug
    return entity_rows, entities_by_slug, index_by_slug, name_to_slug


def clean_content_dir(content_dir: Path, enabled: bool) -> None:
    if enabled and content_dir.exists():
        shutil.rmtree(content_dir)
    ensure_dir(content_dir)


def normalize_internal_target(raw_target: str) -> str:
    target = raw_target.strip()
    if not target:
        return target
    target = target.split("#", 1)[0]
    if target.endswith(".md"):
        target = target[:-3]
    if target.endswith("/index"):
        target = target[:-6]
    return target.strip("/")


def site_link_for_repo_path(path: str) -> str:
    clean = normalize_internal_target(path)
    return clean or "index"


def repo_markdown_to_site_markdown(text: str, source_rel: Path) -> str:
    def replace_md(match: re.Match[str]) -> str:
        label = match.group(1)
        target = match.group(2).strip()
        if target.startswith(("http://", "https://", "mailto:", "#", "<a ")):
            return match.group(0)
        site_target = site_link_for_repo_path(str((source_rel.parent / target).as_posix()))
        return f"[{label}]({site_target})"

    return MD_LINK_RE.sub(replace_md, text)


def write_markdown(dest: Path, content: str, counters: dict[str, int]) -> None:
    ensure_dir(dest.parent)
    dest.write_text(content.rstrip() + "\n", encoding="utf-8")
    counters["generated_files"] += 1


def copy_repo_markdown(repo_path: Path, content_dir: Path, counters: dict[str, int]) -> None:
    rel = repo_path.relative_to(ROOT)
    dest = content_dir / rel
    text = repo_markdown_to_site_markdown(repo_path.read_text(encoding="utf-8"), rel)
    write_markdown(dest, text, counters)
    counters["source_files"] += 1


def markdown_wikilink(target: str, label: str | None = None) -> str:
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def entity_page_target(slug: str) -> str:
    return f"entities/{slug}/index"


def entity_label(row: dict[str, str] | None, index_item: dict[str, object] | None, slug: str) -> str:
    if row and row.get("name"):
        return row["name"]
    if index_item and index_item.get("name"):
        return str(index_item["name"])
    return slug.replace("_", " ").replace("-", " ").title()


def latest_report_paths(base: Path, prefix: str) -> list[Path]:
    if not base.exists():
        return []
    return sorted(base.glob(prefix), reverse=True)


def summarize_entities(entity_rows: list[dict[str, str]]) -> tuple[str, str]:
    active = [row for row in entity_rows if row.get("status", "").lower() == "active"]
    lines = [
        "| Entity | Priority | Type | Status | Connected | Key links |",
        "|---|---:|---|---|---:|---|",
    ]
    for row in sorted(entity_rows, key=lambda r: (r.get("priority", "9"), r.get("name", ""))):
        slug = row.get("slug", "")
        label = row.get("name", slug)
        connected = len([x for x in row.get("connected_entities", "").split("|") if x])
        links = " · ".join([
            markdown_wikilink(entity_page_target(slug), "Landing"),
            markdown_wikilink(f"entities/{slug}/wiki/index", "Wiki"),
            markdown_wikilink(f"entities/{slug}/thesis", "Thesis"),
        ])
        lines.append(f"| {markdown_wikilink(entity_page_target(slug), label)} | {row.get('priority','')} | {row.get('type','')} | {row.get('status','')} | {connected} | {links} |")
    summary = f"- Total entities: {len(entity_rows)}\n- Active entities: {len(active)}"
    return summary, "\n".join(lines)


def summarize_relationships(relationship_rows: list[dict[str, str]], entities_by_slug: dict[str, dict[str, str]]) -> tuple[str, str]:
    type_counts = Counter(row.get("relationship_type") or "related" for row in relationship_rows)
    entity_counts = Counter()
    for row in relationship_rows:
        entity_counts[row.get("source_slug", "")] += 1
        entity_counts[row.get("target_slug", "")] += 1
    summary_lines = [f"- Relationship count: {len(relationship_rows)}", "- Relationship type summary:"]
    for rel_type, count in sorted(type_counts.items()):
        summary_lines.append(f"  - `{rel_type}`: {count}")
    summary_lines.append("- Top connected entities:")
    for slug, count in entity_counts.most_common(10):
        label = entities_by_slug.get(slug, {}).get("name", slug)
        summary_lines.append(f"  - {markdown_wikilink(entity_page_target(slug), label)}: {count}")

    table = [
        "| Source | Target | Type | Importance | Mechanism | Why | Evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in relationship_rows:
        source_slug = row.get("source_slug", "")
        target_slug = row.get("target_slug", "")
        source_name = entities_by_slug.get(source_slug, {}).get("name", source_slug)
        target_name = entities_by_slug.get(target_slug, {}).get("name", target_slug)
        evidence = row.get("evidence_url", "")
        evidence_md = f"[source]({evidence})" if evidence else ""
        table.append(
            f"| {markdown_wikilink(entity_page_target(source_slug), source_name)} | {markdown_wikilink(entity_page_target(target_slug), target_name)} | {row.get('relationship_type','related')} | {row.get('importance','')} | {row.get('mechanism','')} | {row.get('why_connected','')} | {evidence_md} |"
        )
    return "\n".join(summary_lines), "\n".join(table)


def summarize_estimates(estimate_rows: list[dict[str, str]]) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in estimate_rows:
        grouped[row.get("entity_slug", "unknown")].append(row)
    chunks = []
    for slug in sorted(grouped):
        rows = sorted(grouped[slug], key=lambda r: (r.get("year", ""), r.get("metric", "")))
        label = rows[0].get("entity_name", slug)
        chunks.append(f"## {markdown_wikilink(entity_page_target(slug), label)}")
        chunks.append("")
        chunks.append("| Metric | Year | Base | Bearish | Normal | Bullish | Confidence | Source |")
        chunks.append("|---|---:|---|---|---|---|---|---|")
        for row in rows:
            source = row.get("source_url", "")
            source_md = f"[source]({source})" if source else ""
            chunks.append(
                f"| {row.get('metric','')} | {row.get('year','')} | {row.get('base_value','')} | {row.get('bearish_forecast','')} | {row.get('normal_forecast','')} | {row.get('bullish_forecast','')} | {row.get('confidence','')} | {source_md} |"
            )
        chunks.append("")
    return "\n".join(chunks).strip()


def summarize_reports() -> tuple[str, list[Path], list[tuple[str, Path]]]:
    global_reports = sorted((ROOT / "reports" / "daily").glob("report_*.md"), reverse=True)
    entity_reports: list[tuple[str, Path]] = []
    for path in sorted(ENTITIES_DIR.glob("*/daily_reports/report_*.md"), reverse=True):
        entity_reports.append((path.parts[-3], path))
    lines = ["## Latest global daily reports", ""]
    if global_reports:
        for report in global_reports[:20]:
            lines.append(f"- {markdown_wikilink(site_link_for_repo_path(str(report.relative_to(ROOT))), report.name)}")
    else:
        lines.append("- No global daily reports found.")
    lines.extend(["", "## Latest entity daily reports", ""])
    if entity_reports:
        for slug, report in entity_reports[:50]:
            lines.append(f"- {markdown_wikilink(site_link_for_repo_path(str(report.relative_to(ROOT))), f'{slug} · {report.name}')}" )
    else:
        lines.append("- No entity daily reports found.")
    return "\n".join(lines), global_reports, entity_reports


def parse_markdown_internal_edges(content_dir: Path) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for md in sorted(content_dir.rglob("*.md")):
        rel = md.relative_to(content_dir)
        source = normalize_internal_target(rel.as_posix())
        text = md.read_text(encoding="utf-8")
        for target in markdown_links(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_norm = normalize_internal_target((rel.parent / target).as_posix())
            if target_norm:
                edges.append((source, target_norm, "markdown_link"))
        for match in WIKILINK_RE.finditer(text):
            target_norm = normalize_internal_target(match.group(1))
            if target_norm:
                edges.append((source, target_norm, "wikilink"))
    return edges


def generate_graph(
    content_dir: Path,
    graph_json_path: Path,
    entity_rows: list[dict[str, str]],
    entities_by_slug: dict[str, dict[str, str]],
    index_by_slug: dict[str, dict[str, object]],
    name_to_slug: dict[str, str],
    relationship_rows: list[dict[str, str]],
) -> tuple[int, int]:
    nodes: dict[str, dict[str, object]] = {}
    edges_map: dict[tuple[str, str, str], dict[str, object]] = {}

    def ensure_node(node_id: str, label: str | None = None, node_type: str | None = None, priority: str | None = None, exists: bool = False, url: str | None = None) -> None:
        existing = nodes.get(node_id)
        page_path = content_dir / f"entities/{node_id}/index.md"
        node_exists = exists or page_path.exists()
        if existing:
            existing["exists"] = bool(existing.get("exists")) or node_exists
            if label and (existing.get("label") in {None, "", node_id}):
                existing["label"] = label
            if node_type and not existing.get("type"):
                existing["type"] = node_type
            if priority and not existing.get("priority"):
                existing["priority"] = priority
            return
        nodes[node_id] = {
            "id": node_id,
            "label": label or node_id,
            "type": node_type or "related",
            "priority": priority or "",
            "url": url or f"/worldmodel/entities/{node_id}/",
            "exists": node_exists,
        }

    for row in entity_rows:
        slug = row.get("slug", "")
        if not slug:
            continue
        ensure_node(slug, label=row.get("name") or slug, node_type=row.get("type") or "related", priority=row.get("priority", ""), exists=True)

    for row in relationship_rows:
        source = row.get("source_slug", "")
        target = row.get("target_slug", "")
        rel_type = row.get("relationship_type") or "related"
        if not source or not target:
            continue
        ensure_node(source, label=entities_by_slug.get(source, {}).get("name", source), node_type=entities_by_slug.get(source, {}).get("type", "related"), priority=entities_by_slug.get(source, {}).get("priority", ""), exists=source in entities_by_slug)
        ensure_node(target, label=entities_by_slug.get(target, {}).get("name", target), node_type=entities_by_slug.get(target, {}).get("type", "related"), priority=entities_by_slug.get(target, {}).get("priority", ""), exists=target in entities_by_slug)
        key = (source, target, rel_type)
        edges_map[key] = {
            "source": source,
            "target": target,
            "type": rel_type,
            "importance": row.get("importance", "") or "",
            "why": row.get("why_connected", "") or "",
            "evidence_url": canonicalize_url(row.get("evidence_url", "")),
        }

    for slug, item in index_by_slug.items():
        connected = item.get("connected_entities")
        if not isinstance(connected, list):
            connected = []
        for connection in connected:
            label = str(connection.get("name", "")).strip()
            why = str(connection.get("why", "")).strip()
            target = name_to_slug.get(label.lower(), slugify(label))
            ensure_node(slug, label=str(item.get("name", slug)), node_type=str(item.get("type", "related")), priority=str(item.get("priority", "")), exists=slug in entities_by_slug)
            ensure_node(target, label=label, node_type=entities_by_slug.get(target, {}).get("type", "related"), priority=entities_by_slug.get(target, {}).get("priority", ""), exists=target in entities_by_slug)
            key = (slug, target, "related")
            edges_map.setdefault(key, {
                "source": slug,
                "target": target,
                "type": "related",
                "importance": "",
                "why": why,
                "evidence_url": "",
            })

    for source_page, target_page, edge_type in parse_markdown_internal_edges(content_dir):
        source_slug = source_page.split("/")[1] if source_page.startswith("entities/") and len(source_page.split("/")) > 1 else source_page
        target_slug = target_page.split("/")[1] if target_page.startswith("entities/") and len(target_page.split("/")) > 1 else target_page
        ensure_node(source_slug, label=entities_by_slug.get(source_slug, {}).get("name", source_slug), node_type=entities_by_slug.get(source_slug, {}).get("type", "page"), priority=entities_by_slug.get(source_slug, {}).get("priority", ""), exists=source_slug in entities_by_slug)
        ensure_node(target_slug, label=entities_by_slug.get(target_slug, {}).get("name", target_slug), node_type=entities_by_slug.get(target_slug, {}).get("type", "page"), priority=entities_by_slug.get(target_slug, {}).get("priority", ""), exists=target_slug in entities_by_slug)
        key = (source_slug, target_slug, edge_type if edge_type != "markdown_link" else "related")
        edges_map.setdefault(key, {
            "source": source_slug,
            "target": target_slug,
            "type": key[2],
            "importance": "",
            "why": f"Derived from {edge_type.replace('_', ' ')} between generated site pages.",
            "evidence_url": "",
        })

    payload = {
        "generated_at": now_utc(),
        "nodes": sorted(nodes.values(), key=lambda item: str(item["id"])),
        "edges": sorted(edges_map.values(), key=lambda item: (str(item["source"]), str(item["target"]), str(item["type"]))),
    }
    ensure_dir(graph_json_path.parent)
    graph_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(payload["nodes"]), len(payload["edges"])


def build_home_page(entity_rows: list[dict[str, str]], global_reports: list[Path]) -> str:
    priority_entities = [row for row in entity_rows if row.get("priority") in {"1", "P0", "0"} or row.get("priority") == "1"]
    if not priority_entities:
        priority_entities = sorted(entity_rows, key=lambda row: (row.get("priority", "9"), row.get("name", "")))[:12]
    latest_lines = []
    for report in global_reports[:10]:
        latest_lines.append(f"- {markdown_wikilink(site_link_for_repo_path(str(report.relative_to(ROOT))), report.name)}")
    if not latest_lines:
        latest_lines = ["- No reports yet."]
    priority_lines = [f"- {markdown_wikilink(entity_page_target(row['slug']), row.get('name', row['slug']))} ({row.get('type','')}, priority {row.get('priority','')})" for row in sorted(priority_entities, key=lambda row: (row.get('priority','9'), row.get('name','')))]
    return "\n".join([
        "# WorldModel",
        "",
        "WorldModel tracks companies, sectors, markets, people, technologies, commodities, and their relationships.",
        "",
        "## Main sections",
        "",
        "- [[entities]]",
        "- [[graph]]",
        "- [[relationships]]",
        "- [[estimates]]",
        "- [[reports]]",
        "",
        "## Priority entities",
        "",
        *priority_lines,
        "",
        "## Latest reports",
        "",
        *latest_lines,
        "",
        "## Graph",
        "",
        "Open [[graph]] to inspect relationships.",
    ])


def build_graph_page(node_count: int, edge_count: int) -> str:
    return "\n".join([
        "# WorldModel Graph",
        "",
        "Quartz renders the interactive local and global graph from internal links. This repository also exports structured graph metadata to [[worldmodel_graph.json]].",
        "",
        f"- Nodes: {node_count}",
        f"- Edges: {edge_count}",
        "- Use the right-hand graph panel on desktop or scroll below the article on mobile.",
        "- Open entity landing pages for denser backlinks and local-neighborhood navigation.",
    ])


def build_entity_landing(
    slug: str,
    row: dict[str, str],
    index_item: dict[str, object] | None,
    outgoing: list[dict[str, str]],
    incoming: list[dict[str, str]],
    entity_reports: list[Path],
) -> str:
    name = row.get("name", slug)
    summary = row.get("description") or str(index_item.get("notes", "")) if index_item else row.get("description", "")
    summary = summary or f"{name} tracked by WorldModel."
    lines = [
        f"# {name}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Files",
        "",
        f"- {markdown_wikilink(f'entities/{slug}/wiki/index', 'Wiki')}",
        f"- {markdown_wikilink(f'entities/{slug}/thesis', 'Thesis')}",
        f"- {markdown_wikilink(f'entities/{slug}/financial_report', 'Financial report')}",
        "",
        "## Connected entities",
        "",
    ]
    if outgoing or incoming:
        for rel in outgoing:
            target_slug = rel.get("target_slug", "")
            target_name = rel.get("target_name", target_slug)
            lines.append(f"- {markdown_wikilink(entity_page_target(slug), name)} → {markdown_wikilink(entity_page_target(target_slug), target_name)}: {rel.get('why_connected') or rel.get('mechanism') or rel.get('relationship_type') or 'related'}")
        for rel in incoming:
            source_slug = rel.get("source_slug", "")
            source_name = rel.get("source_name", source_slug)
            lines.append(f"- {markdown_wikilink(entity_page_target(source_slug), source_name)} → {markdown_wikilink(entity_page_target(slug), name)}: {rel.get('why_connected') or rel.get('mechanism') or rel.get('relationship_type') or 'related'}")
    else:
        lines.append("- No connected entities recorded yet.")
    lines.extend(["", "## Latest reports", ""])
    if entity_reports:
        for report in entity_reports[:10]:
            lines.append(f"- {markdown_wikilink(site_link_for_repo_path(str(report.relative_to(ROOT))), report.name)}")
    else:
        lines.append("- No entity daily reports yet.")
    lines.extend([
        "",
        "## Source repository paths",
        "",
        f"- `entities/{slug}/wiki/index.md`",
        f"- `entities/{slug}/thesis.md`",
        f"- `entities/{slug}/financial_report.md`",
    ])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    content_dir = Path(args.content_dir).resolve()
    graph_json_path = Path(args.graph_json).resolve() if args.graph_json else (content_dir / "worldmodel_graph.json")
    should_clean = args.clean and not args.no_clean

    verify_repo_inputs(args.strict)
    clean_content_dir(content_dir, should_clean)
    ensure_dir(SITE_DIR)

    counters = {"source_files": 0, "generated_files": 0}
    warnings: list[str] = []

    entity_rows, entities_by_slug, index_by_slug, name_to_slug = load_entities()
    relationship_rows = read_csv(DATA_DIR / "relationships.csv")
    estimate_rows = read_csv(DATA_DIR / "estimates.csv")

    for file_name in ROOT_MARKDOWN_COPIES:
        repo_file = ROOT / file_name
        if repo_file.exists():
            copy_repo_markdown(repo_file, content_dir, counters)

    repo_index_copy = ROOT / "index.md"
    write_markdown(content_dir / "repo_index.md", repo_markdown_to_site_markdown(repo_index_copy.read_text(encoding="utf-8"), Path("index.md")), counters)
    counters["source_files"] += 1

    missing_entity_files = []
    relationship_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    relationship_by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in relationship_rows:
        src = row.get("source_slug", "")
        dst = row.get("target_slug", "")
        enriched = dict(row)
        enriched["source_name"] = entities_by_slug.get(src, {}).get("name", src)
        enriched["target_name"] = entities_by_slug.get(dst, {}).get("name", dst)
        relationship_by_source[src].append(enriched)
        relationship_by_target[dst].append(enriched)

    entity_page_count = 0
    for slug, row in sorted(entities_by_slug.items(), key=lambda item: (item[1].get("priority", "9"), item[1].get("name", item[0]))):
        entity_dir = ENTITIES_DIR / slug
        if not entity_dir.exists():
            missing_entity_files.append(str(entity_dir))
            continue
        for wiki_page in WIKI_PAGES:
            page = entity_dir / "wiki" / wiki_page
            if not page.exists():
                missing_entity_files.append(str(page))
            else:
                copy_repo_markdown(page, content_dir, counters)
        for file_name in REQUIRED_ENTITY_FILES:
            page = entity_dir / file_name
            if not page.exists():
                missing_entity_files.append(str(page))
            elif page.suffix == ".md":
                copy_repo_markdown(page, content_dir, counters)
        for report in latest_report_paths(entity_dir / "daily_reports", "report_*.md"):
            copy_repo_markdown(report, content_dir, counters)
        landing = build_entity_landing(
            slug,
            row,
            index_by_slug.get(slug),
            relationship_by_source.get(slug, []),
            relationship_by_target.get(slug, []),
            latest_report_paths(entity_dir / "daily_reports", "report_*.md"),
        )
        write_markdown(content_dir / "entities" / slug / "index.md", landing, counters)
        entity_page_count += 1

    for report in latest_report_paths(ROOT / "reports" / "daily", "report_*.md"):
        copy_repo_markdown(report, content_dir, counters)
    for report in latest_report_paths(ROOT / "reports", "report_*.md"):
        copy_repo_markdown(report, content_dir, counters)

    reports_body, global_reports, entity_reports = summarize_reports()
    home_body = build_home_page(entity_rows, global_reports)
    entity_summary, entity_table = summarize_entities(entity_rows)
    rel_summary, rel_table = summarize_relationships(relationship_rows, entities_by_slug)
    estimate_body = summarize_estimates(estimate_rows)

    write_markdown(content_dir / "index.md", home_body, counters)
    write_markdown(content_dir / "entities.md", f"# Entities\n\n{entity_summary}\n\n{entity_table}\n", counters)
    write_markdown(content_dir / "relationships.md", f"# Relationships\n\n{rel_summary}\n\n{rel_table}\n", counters)
    write_markdown(content_dir / "estimates.md", f"# Estimates\n\n{estimate_body}\n", counters)
    write_markdown(content_dir / "reports.md", f"# Reports\n\n{reports_body}\n", counters)

    node_count, edge_count = generate_graph(content_dir, graph_json_path, entity_rows, entities_by_slug, index_by_slug, name_to_slug, relationship_rows)
    write_markdown(content_dir / "graph.md", build_graph_page(node_count, edge_count), counters)

    if missing_entity_files:
        warnings.extend(f"missing entity file: {item}" for item in missing_entity_files)
        if args.strict:
            raise SystemExit("strict mode failed: missing required entity files")
    if node_count == 0:
        fail("generated graph has zero nodes", args.strict)
    if entity_page_count == 0:
        fail("generated site content has no entity pages", args.strict)

    print("site preparation summary:")
    print(f"- source files processed: {counters['source_files']}")
    print(f"- generated content files: {counters['generated_files']}")
    print(f"- entity landing pages: {entity_page_count}")
    print(f"- graph nodes: {node_count}")
    print(f"- graph edges: {edge_count}")
    print("- warnings:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
