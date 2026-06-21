---
name: worldmodel
description: "Operate the WorldModel repository: initialize entities, retrieve sources, rank, update structured data, render docs, and commit deterministic changes."
version: 0.1.0
author: Hermes Agent
license: MIT
---

# WorldModel

Use this skill when working inside the `Kabutojira/worldmodel` repository.

## Principles

- The repository is the source of truth.
- Use deterministic scripts before LLM reasoning.
- Do not store full copyrighted articles.
- Cite sources with URLs.
- Read at most 10 new sources per entity per daily run.
- Separate evidence from inference.
- Keep bearish, normal, and bullish scenarios aligned across Markdown and CSV.
- Update relationships after entity changes.
- Save daily reports as `report_YYYY-MM-DD.md`.
- Include Markdown links to modified files and HTML links to sources.

## Commands

Run from repository root.

### 1. Initialize entity

```bash
python3 bin/worldmodel_init_entity.py --name "Entity Name" --slug entity-slug --type company --ticker TICK --priority 3
```

### 2. Retrieve daily sources

```bash
python3 bin/worldmodel_retrieve.py --all-active --since-last-report --out .worldmodel/candidates.json
```

Current adapters include:

- investor relations / official pages;
- SEC filings and companyfacts for Tesla seed;
- deterministic Seeking Alpha symbol / analysis / transcript endpoints by ticker;
- curated Substack RSS watchlist ingestion from tracked config `data/substack_watchlist.csv`; active rows require semicolon-delimited keywords and fresh `last_checked_at` dates;
- YouTube channel metadata candidates sourced from:
  - All-In Podcast;
  - The Limiting Factor.

### 2b. Fetch local YouTube transcript cache

Keep full transcripts out of the git-tracked repository. Cache them under `.worldmodel/` for LLM reading and citation extraction.

```bash
python3 bin/worldmodel_youtube_transcripts.py --channel all-in --channel the-limiting-factor --max-videos 3 --keywords "Tesla,TSLA,Elon,FSD,robotaxi,4680,Megapack,Supercharger"
```

Run transcript fetch before retrieval if you want `worldmodel_retrieve.py` to see cached transcript paths.

### 3. Rank sources

```bash
python3 bin/worldmodel_rank_sources.py --in .worldmodel/candidates.json --out .worldmodel/selected.json --limit-per-entity 10
```

### 4. Process selected sources with LLM

1. Read `.worldmodel/selected.json`.
2. Open the linked primary sources first.
3. Extract evidence, affected metrics, thesis implications, and related entities.
4. Update the entity wiki pages before thesis/report summaries.

### 5. Update wiki pages

- `entities/<slug>/wiki/index.md`
- `entities/<slug>/wiki/business.md`
- `entities/<slug>/wiki/market.md`
- `entities/<slug>/wiki/financials.md`
- `entities/<slug>/wiki/technology.md`
- `entities/<slug>/wiki/people.md`
- `entities/<slug>/wiki/risks.md`
- `entities/<slug>/wiki/sources.md`

### 6. Update thesis

Keep the three scenario sections synchronized with any estimate changes.

### 7. Update estimates CSV

```bash
python3 bin/worldmodel_update_csv.py --validate --merge-all
```

### 8. Update relationships

Edit `data/relationships.csv` and the relevant `index.md` connection notes. Every relationship needs mechanism, why_connected, and evidence_url.

### 9. Generate daily report

```bash
python3 bin/worldmodel_generate_report.py --selected .worldmodel/selected.json
```

Create:

- `reports/daily/report_YYYY-MM-DD.md`
- `entities/<slug>/daily_reports/report_YYYY-MM-DD.md` for changed entities.

Required sections:

- run date;
- entities processed;
- selected sources with HTML links;
- skipped sources with reasons;
- modified files with Markdown links;
- facts added;
- thesis changes;
- CSV updates;
- relationship changes;
- mispricing/tendency signals;
- open questions;
- next actions.

### 10. Render GitHub Pages

```bash
python3 bin/worldmodel_render_site.py
```

### 11. Run maintenance

```bash
python3 bin/worldmodel_maintenance.py --strict
```

### 12. Commit and push

```bash
python3 bin/worldmodel_commit.py --message "Update worldmodel daily report $(date -I)"
```

## Recovery guidance

- If retrieval fails, inspect network/API access and rerun retrieval only.
- If ranking fails, validate `.worldmodel/candidates.json` first.
- If CSV validation fails, fix schemas before changing wiki/report text.
- If rendering fails, repair markdown links or malformed front matter before committing.
- If maintenance fails in strict mode, resolve the listed findings or document why the run is intentionally partial.
