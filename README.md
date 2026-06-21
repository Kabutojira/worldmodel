# WorldModel

WorldModel is a research repository and daily intelligence workflow for tracking companies, sectors, markets, technologies, commodities, infrastructure, and people as a connected investment graph.

## What it does

- tracks entities in Markdown and CSV, with the repository as source of truth;
- maintains per-entity wiki, thesis, financial report, estimates, and daily reports;
- ranks new sources every day;
- preserves a deterministic source history so the same source is not repeatedly surfaced as new work;
- renders a public Quartz site to GitHub Pages.

## Repository map

- `index.md` — canonical human-readable registry of tracked entities and why they matter.
- `data/entities.csv` — entity overview table.
- `data/relationships.csv` — directed relationship graph with mechanism and evidence.
- `data/estimates.csv` — scenario and forecast table.
- `data/source_log.csv` — metadata for sources that were logged/used.
- `data/source_history.csv` — deterministic source-state history across runs.
- `data/source_registry.csv` — systematic watchlist of sources to scan daily/weekly.
- `entities/<slug>/` — wiki, thesis, financial report, source log, and daily reports for each entity.
- `reports/daily/` — global daily intelligence reports.
- `site/` — Quartz site configuration and generated content/build artifacts.

## Daily workflow

Typical deterministic pipeline:

```bash
python3 bin/worldmodel_retrieve.py --all-active --since-last-report --out .worldmodel/candidates.json
python3 bin/worldmodel_rank_sources.py --in .worldmodel/candidates.json --out .worldmodel/selected.json --limit-per-entity 10
python3 bin/worldmodel_generate_report.py --selected .worldmodel/selected.json
python3 bin/worldmodel_maintenance.py --strict
python3 bin/worldmodel_render_site.py --clean --strict
```

Then the synthesis step updates entity content from selected sources and commits the result.

## Source rules

- Do not store full copyrighted articles in git.
- Store metadata, short summaries, extracted facts, dates, and URLs.
- Prefer primary sources.
- Treat X and commentary as signal generation, not ground truth.
- Keep investment conclusions explicitly separated into evidence vs inference.

## Source registry

`data/source_registry.csv` is the systematic watchlist for recurring scans.

Columns:

- `source_id`
- `platform`
- `name`
- `url`
- `priority`
- `entities`
- `source_type`
- `quality_notes`
- `bias_notes`
- `retrieval_frequency`

Current tracked examples include The Limiting Factor, SemiAnalysis, Fabricated Knowledge, Interconnects AI, Volts, Commodity Context, and selected X accounts.

## Public site

The GitHub Pages site is built from repository content via Quartz.

Expected URL:

- <https://kabutojira.github.io/worldmodel/>

For operator notes, see [`SITE.md`](SITE.md).
