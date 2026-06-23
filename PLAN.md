# PLAN.md

## Project: WorldModel

Goal: build a Hermes-maintained research repository that tracks companies, sectors, markets, people, commodities, technologies, and their relationships. The system must retrieve high-quality sources daily, update llm-wiki knowledge bases, maintain structured CSV estimates, detect thesis changes and market mispricing signals, generate daily reports, render Markdown to GitHub Pages, and commit/push changes to `https://github.com/Kabutojira/worldmodel`.

## Operating assumptions

- Repository: `Kabutojira/worldmodel`.
- First active entity: Tesla.
- Hermes profile has access to the repository checkout and Git credentials.
- The repository is the source of truth.
- Google Sheets is used as a view/editor over CSV exports, not as the source of truth.
- Markdown and CSV files remain human-readable and diff-friendly.
- Full copyrighted articles are not stored; only metadata, short summaries, extracted facts, and source URLs are retained.
- Scripts perform deterministic work; LLMs perform synthesis and judgment.

## Target repository state

Create this initial structure:

```text
/
├── README.md
├── AGENTS.md
├── PLAN.md
├── index.md
├── data/
│   ├── entities.csv
│   ├── relationships.csv
│   ├── estimates.csv
│   ├── source_log.csv
│   ├── source_history.csv
│   ├── source_registry.csv
│   └── daily_runs.csv
├── templates/
│   ├── entity.md
│   ├── financial_report.md
│   ├── thesis.md
│   ├── daily_report.md
│   └── entity_row.csv
├── entities/
│   └── tesla/
│       ├── wiki/
│       │   ├── index.md
│       │   ├── business.md
│       │   ├── market.md
│       │   ├── financials.md
│       │   ├── technology.md
│       │   ├── people.md
│       │   ├── risks.md
│       │   └── sources.md
│       ├── thesis.md
│       ├── financial_report.md
│       ├── estimates.csv
│       ├── source_log.csv
│       └── daily_reports/
├── reports/
│   └── daily/
├── skills/
│   └── worldmodel/
│       └── SKILL.md
├── bin/
│   ├── worldmodel_init_entity.py
│   ├── worldmodel_retrieve.py
│   ├── worldmodel_rank_sources.py
│   ├── worldmodel_update_csv.py
│   ├── worldmodel_generate_report.py
│   ├── worldmodel_render_site.py
│   ├── worldmodel_maintenance.py
│   └── worldmodel_commit.py
├── site/
│   ├── package.json
│   ├── package-lock.json
│   ├── quartz.config.yaml
│   ├── quartz.layout.ts
│   ├── content/
│   └── public/
└── docs/
```

## Milestone 1 — Bootstrap repository conventions

### Tasks

1. Add `AGENTS.md` with project rules, file contracts, daily workflow, entity workflow, source rules, and done criteria.
2. Add `PLAN.md` with this implementation plan.
3. Create `index.md` with a Tesla entry and initial connected entities.
4. Create `data/` CSV files with headers only, plus Tesla seed rows where safe.
5. Create `templates/` files for entity wiki, thesis, financial report, daily report, and CSV row examples.
6. Create `entities/tesla/` directory and all required seed files.
7. Create empty `reports/daily/` and Quartz `site/` scaffolding, preserving any placeholder directories with `.gitkeep` if needed.

### Acceptance criteria

- `index.md` contains Tesla with search keywords and explained connected entities.
- All CSV files have stable headers.
- Tesla has a complete entity directory.
- Required templates exist.
- `AGENTS.md` and `PLAN.md` match the repository layout.

## Milestone 2 — Implement deterministic scripts

### `bin/worldmodel_init_entity.py`

Purpose: create a new entity from templates.

Required behavior:

- accept `--name`, `--slug`, `--type`, `--ticker`, `--priority`;
- create `entities/<slug>/`;
- create wiki pages from templates;
- append row to `data/entities.csv` if missing;
- refuse duplicate slugs;
- optionally add seed relationships.

### `bin/worldmodel_retrieve.py`

Purpose: collect candidate source metadata for each active entity.

Completed improvements on 2026-06-21:

- retrieval now only seeds synthetic investor-relations URLs for company-like entities (`company`, `private_company`, `supplier`, `customer`) so thematic nodes such as markets, sectors, people, and commodities are not polluted by fake IR placeholders.
- retrieval now resolves SEC CIKs dynamically for US tickers and discovers the latest 10-K, 10-Q, recent 8-Ks, and exhibit-driven quarterly update / delivery documents from `data.sec.gov` instead of relying on static Tesla-only filing URLs.

Completed improvement on 2026-06-22:

- retrieval now crawls issuer homepages for company-like entities, records official site / newsroom / investor links when discoverable, and only falls back to synthetic IR URLs when homepage discovery fails.

Required behavior:

- parse `index.md` and `data/entities.csv`;
- determine last retrieval/report time;
- search configured source families;
- collect candidate URLs and metadata;
- deduplicate by canonical URL and hash;
- store source metadata only;
- emit JSON for LLM processing.

Initial source adapters:

- generic web search adapter;
- investor-relations discovery adapter;
- SEC/EDGAR adapter for US-listed companies;
- RSS/feed adapter where available;
- manual URL ingestion adapter.

Optional adapters:

- Seeking Alpha adapter, subject to available credentials and terms;
- X adapter, subject to available API or export access.

### `bin/worldmodel_rank_sources.py`

Purpose: rank candidate sources before LLM reading.

Required behavior:

- score quality, recency, relevance;
- select maximum 10 sources per entity since last report;
- prefer primary sources;
- output selected and skipped sources with reasons.

### `bin/worldmodel_update_csv.py`

Purpose: safely update structured CSVs.

Required behavior:

- validate schemas;
- merge entity-level estimates into `data/estimates.csv`;
- sort rows deterministically;
- preserve manually entered notes;
- validate forecast scenario fields;
- write atomically.

### `bin/worldmodel_generate_report.py`

Purpose: generate deterministic global and per-entity daily report skeletons from ranked source output.

Completed improvement on 2026-06-21:

- daily report scaffolds now quarantine operational and maintenance details in an appendix so the main body can be rewritten as content-first investment intelligence rather than a pipeline log.

Required behavior:

- read ranked selection JSON;
- generate `reports/daily/report_YYYY-MM-DD.md`;
- generate `entities/<slug>/daily_reports/report_YYYY-MM-DD.md` for ranked entities;
- include selected sources, skipped sources, modified-file links, and issue/inefficiency notes;
- fail loudly when ranked input is missing or malformed.

### `bin/worldmodel_render_site.py`

Purpose: prepare Quartz-compatible Markdown under `site/content/` and let Quartz build GitHub Pages HTML under `site/public/`.

Required behavior:

- generate site index;
- generate entity pages;
- generate daily report pages;
- generate estimates and relationships pages;
- preserve source links;
- avoid manual-only state in generated files;
- keep repository Markdown and CSVs as the source of truth.

### `bin/worldmodel_maintenance.py`

Purpose: detect repository drift and maintenance needs.

Completed improvement on 2026-06-21:

- maintenance now verifies source-state consistency between `data/source_log.csv`, per-entity `source_log.csv` files, `data/source_history.csv` references in the latest global daily report, and the existence of the latest global report artifact.

Required behavior:

- check missing files;
- check malformed CSV;
- check broken internal Markdown links;
- check relationships missing explanations;
- check estimates missing bearish/normal/bullish fields;
- check duplicate sources;
- check reports missing source links or modified-file links;
- output actionable maintenance findings.

### `bin/worldmodel_commit.py`

Purpose: commit and push deterministic changes.

Required behavior:

- show status;
- refuse empty commit unless `--allow-empty`;
- use standardized commit messages;
- push to configured remote;
- return non-zero on failure.

### Acceptance criteria

- Scripts run without LLM access.
- Scripts are idempotent.
- Scripts can be called by Hermes skills and cron jobs.
- Scripts fail loudly on invalid schemas.

## Milestone 3 — Create Hermes skill

Create `skills/worldmodel/SKILL.md`.

The skill must expose these operations:

1. initialize entity;
2. retrieve daily sources;
3. rank sources;
4. process selected sources with LLM;
5. update wiki pages;
6. update thesis;
7. update estimates CSV;
8. update relationships;
9. generate daily report;
10. render GitHub Pages;
11. run maintenance;
12. commit and push.

The skill must instruct the agent to:

- use scripts before LLM reasoning;
- keep full articles out of the repository;
- cite sources with URLs;
- cap reading to 10 sources per entity per daily run;
- explicitly distinguish evidence from inference;
- keep bullish, normal, and bearish scenarios aligned across Markdown and CSV;
- update relationships after entity changes;
- save daily reports as `report_YYYY-MM-DD.md`;
- include Markdown links to modified files and HTML links to sources.

### Acceptance criteria

- Hermes can run the daily workflow from the skill alone.
- Skill references the exact scripts and file paths.
- Skill includes recovery instructions for partial failures.

## Milestone 4 — Seed Tesla

### Tesla files to create

```text
entities/tesla/wiki/index.md
entities/tesla/wiki/business.md
entities/tesla/wiki/market.md
entities/tesla/wiki/financials.md
entities/tesla/wiki/technology.md
entities/tesla/wiki/people.md
entities/tesla/wiki/risks.md
entities/tesla/wiki/sources.md
entities/tesla/thesis.md
entities/tesla/financial_report.md
entities/tesla/estimates.csv
entities/tesla/source_log.csv
```

### Tesla initial source discovery

Search and seed from:

- Tesla Investor Relations;
- latest annual report;
- latest quarterly report;
- latest earnings release;
- latest earnings-call transcript;
- latest investor presentation if available;
- delivery and production releases;
- energy storage deployment disclosures;
- major FSD/robotaxi public materials;
- Optimus public materials;
- battery supply and lithium materials;
- high-quality independent deep dives.

### Tesla initial connected entities

Add and explain at least these relationships:

- Tesla → lithium: battery input cost and supply availability affect EV and storage margins.
- Tesla → automotive market: core revenue pool and cyclical demand benchmark.
- Tesla → EV market: adoption curve, policy incentives, and competition directly affect growth.
- Tesla → battery storage market: Megapack and grid storage growth drive Tesla Energy optionality.
- Tesla → autonomous driving / robotaxi: major optionality and valuation narrative.
- Tesla → humanoid robotics / Optimus: long-term optionality and AI/robotics narrative.
- Tesla → charging infrastructure: ecosystem moat, network effects, and service revenue.
- Tesla → Panasonic: historical battery supplier relationship.
- Tesla → CATL: battery supply and chemistry benchmark.
- Tesla → LG Energy Solution: battery supply relationship.
- Tesla → BYD: EV competitor and battery competitor.
- Tesla → Nvidia: AI compute/autonomy benchmark and possible dependency signal.
- Tesla → Elon Musk: key-person, governance, capital-market narrative, and brand influence.

### Acceptance criteria

- Tesla appears in `index.md` and `data/entities.csv`.
- Tesla has a populated wiki skeleton.
- Tesla has a first `thesis.md` with bearish, normal, and bullish sections.
- Tesla has a first `financial_report.md`.
- Tesla relationships are present in `data/relationships.csv` with mechanisms and evidence placeholders or links.

## Milestone 5 — Daily run workflow

Implement and test the daily run:

```bash
python3 bin/worldmodel_retrieve.py --all-active --since-last-report --out .worldmodel/candidates.json
python3 bin/worldmodel_rank_sources.py --in .worldmodel/candidates.json --out .worldmodel/selected.json --limit-per-entity 10
# Hermes LLM step: read selected sources, update wiki/thesis/reports/relationships.
python3 bin/worldmodel_generate_report.py --selected .worldmodel/selected.json
python3 bin/worldmodel_update_csv.py --validate --merge-all
python3 bin/worldmodel_maintenance.py --strict
python3 bin/worldmodel_render_site.py
python3 bin/worldmodel_commit.py --message "Update worldmodel daily report $(date -I)"
```

### Daily report contract

Global report path:

```text
reports/daily/report_YYYY-MM-DD.md
```

Per-entity report path:

```text
entities/<slug>/daily_reports/report_YYYY-MM-DD.md
```

Each report must include:

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

### Acceptance criteria

- Running the workflow twice without new sources does not create noisy diffs.
- A source already processed is skipped on the next run.
- The report contains source links and modified-file links.
- The site renders.
- Commit and push work from the Hermes environment.

## Milestone 6 — Recursive entity expansion

When Tesla source processing identifies a material dependency, create related entities recursively only when the connection has direct thesis impact.

Priority expansion candidates:

1. lithium;
2. automotive market;
3. EV market;
4. battery storage market;
5. autonomous driving / robotaxi;
6. humanoid robotics;
7. BYD;
8. CATL;
9. Panasonic;
10. LG Energy Solution;
11. Nvidia;
12. Elon Musk.

Expansion rules:

- Add no more than 3 new active entities per daily run unless manually requested.
- New entities may start as `status: paused` if they are useful context but not yet tracked daily.
- Every new entity must have at least one relationship explaining why it exists.
- Do not track weakly related entities.

### Acceptance criteria

- Related entities are added deliberately, not explosively.
- Every active entity has keywords, source priority, relationships, and file skeletons.

## Milestone 7 — GitHub Pages publishing

Use Quartz with generated Markdown in `site/content/` and build output in `site/public/`.

Required pages:

- home page with entity list;
- entity pages;
- relationships page;
- estimates page;
- daily reports page;
- source-log page or summarized source index.

Rendering requirements:

- deterministic output;
- internal links preserved;
- external source links preserved;
- no generated page should require manual editing;
- generated files should remain uncommitted unless a later publishing requirement explicitly changes that rule.

### Acceptance criteria

- GitHub Pages can publish from the workflow artifact built from `site/public/`.
- Local Markdown remains the editing source of truth.
- Generated HTML includes report navigation.

## Milestone 8 — Maintenance loop

Add a maintenance run after daily updates.

Maintenance must check:

- `AGENTS.md` and `PLAN.md` still match actual structure;
- scripts match CSV schemas;
- templates include all fields used by scripts;
- daily report format is valid;
- entity directories are complete;
- source logs are deduplicated;
- links work;
- generated site is current.

When maintenance changes are needed:

1. create or update scripts/templates/docs;
2. add a maintenance section to the daily report;
3. commit with message `Maintain worldmodel automation` or include maintenance in the daily commit.

### Acceptance criteria

- Maintenance detects drift before it corrupts data.
- Maintenance findings are visible in daily reports.

## Next steps to make the project better

- Add an automated, compliant collector that refreshes `.worldmodel/x_post_import.csv` from allowed exports or API access so X account coverage no longer depends on manual post URL seeding.

## Initial `index.md` seed

```md
# WorldModel Entity Index

This file is the canonical registry of tracked entities, search keywords, and connected entities.

## Tesla

- Slug: tesla
- Type: company
- Status: active
- Priority: 1
- Search keywords:
  - "Tesla investor relations"
  - "Tesla 10-K"
  - "Tesla 10-Q"
  - "Tesla earnings call transcript"
  - "Tesla vehicle deliveries"
  - "Tesla automotive gross margin"
  - "Tesla energy storage deployments"
  - "Tesla Megapack backlog"
  - "Tesla FSD robotaxi"
  - "Tesla Optimus humanoid robot"
  - "Tesla lithium supply"
  - "Tesla battery suppliers"
- Source priority:
  - investor relations
  - filings
  - earnings calls
  - investor presentations
  - delivery reports
  - Seeking Alpha deep dives
  - X high-signal posts
  - trade publications
- Connected entities:
  - Lithium: battery input cost and supply availability affect Tesla EV and storage margins.
  - Automotive market: Tesla automotive revenue depends on global light-vehicle demand, pricing, and financing conditions.
  - EV market: adoption curve, incentives, charging infrastructure, and EV competition affect Tesla growth.
  - Battery storage market: Megapack and grid storage growth affect Tesla Energy revenue and margin potential.
  - Autonomous driving / robotaxi: FSD and robotaxi expectations are central to Tesla optionality and valuation narrative.
  - Humanoid robotics / Optimus: long-duration optionality linked to robotics, manufacturing automation, and AI.
  - Charging infrastructure: Supercharger network affects ecosystem lock-in, service revenue, and EV adoption.
  - Panasonic: historical battery supplier and production partner.
  - CATL: battery supplier/benchmark for cost, chemistry, and supply chain.
  - LG Energy Solution: battery supplier and cell technology peer.
  - BYD: EV competitor, battery competitor, and China demand benchmark.
  - Nvidia: AI compute/autonomy benchmark and possible dependency signal.
  - Elon Musk: key-person, governance, brand, and market narrative influence.
- Last retrieval:
- Last report:
- Notes: Initial seed entity. Track automotive, energy, autonomy, robotics, battery supply, and key-person narrative.
```

## Initial CSV headers

### `data/entities.csv`

```csv
entity_id,slug,name,type,status,priority,ticker,exchange,currency,geography,sector,industry,business_lines,description,search_keywords,connected_entities,last_retrieval_at,last_report_date,last_source_count,confidence,owner_notes
```

### `data/relationships.csv`

```csv
source_slug,target_slug,relationship_type,direction,importance,mechanism,why_connected,evidence_url,last_reviewed_at,confidence
```

### `data/estimates.csv`

```csv
entity_slug,entity_name,type,business_line,metric,unit,currency,actual_or_estimate,year,base_value,bearish_forecast,normal_forecast,bullish_forecast,bearish_thesis,normal_thesis,bullish_thesis,source_url,source_date,updated_at,confidence,notes
```

### `data/source_log.csv`

```csv
source_id,entity_slug,title,source_name,source_type,url,author,published_at,retrieved_at,quality_score,recency_score,relevance_score,used_in_update,summary_path,hash,notes
```

### `data/source_history.csv`

```csv
history_key,source_id,entity_slug,title,source_name,source_type,url,first_seen_at,last_seen_at,last_selected_at,last_used_at,times_seen,times_selected,times_used,current_state,notes
```

### `data/source_registry.csv`

```csv
source_id,platform,name,url,priority,entities,source_type,quality_notes,bias_notes,retrieval_frequency
```

### `data/daily_runs.csv`

```csv
run_id,run_date,started_at,finished_at,status,entities_processed,sources_selected,files_changed,commit_sha,notes
```

## Commit plan

After bootstrap:

```bash
git add AGENTS.md PLAN.md index.md data templates entities reports skills bin docs
git commit -m "Bootstrap worldmodel project"
git push
```

After Tesla seeding:

```bash
git add index.md data entities/tesla reports docs
git commit -m "Seed Tesla entity"
git push
```

After daily runs:

```bash
git add index.md data entities reports site .github/workflows/pages.yml SITE.md
git commit -m "Update worldmodel daily report YYYY-MM-DD"
git push
```

## Definition of done

The project is operational when:

- Tesla is seeded as the first active entity;
- all required directories and files exist;
- CSV schemas are stable;
- the Hermes skill can run retrieval and update steps;
- deterministic scripts handle non-LLM tasks;
- daily report generation works;
- GitHub Pages rendering works;
- daily commits are pushed to `Kabutojira/worldmodel`;
- maintenance checks run after daily updates.
