# AGENTS.md

## Project: WorldModel

WorldModel is a Hermes project for tracking companies, sectors, markets, people, technologies, and commodities as connected entities. The repository is both a research memory and a recurring market-monitoring workflow.

The system must maintain:

- a canonical entity registry in `index.md`;
- normalized CSV datasets for current facts, historical estimates, and future scenarios;
- one llm-wiki-style knowledge base per entity;
- one maintained financial report per entity;
- daily reports for new information and changed files;
- a generated GitHub Pages site rendered from the Markdown repository.

Use scripts for deterministic work and LLM reasoning only where synthesis, classification, thesis updates, or judgment are required.

## Repository layout

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
│   └── <entity_slug>/
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
│           └── report_YYYY-MM-DD.md
├── reports/
│   └── daily/
│       └── report_YYYY-MM-DD.md
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
│   │   └── generated Quartz content from repository Markdown and CSVs
│   └── public/
│       └── generated Quartz build output for GitHub Pages
└── docs/
    └── optional legacy output; Quartz now publishes from `site/public/`
```

## Canonical files

### `index.md`

`index.md` is the canonical human-readable registry of tracked entities.

Each entity entry must contain:

```md
## <Entity Name>

- Slug: <entity_slug>
- Type: company | sector | market | person | commodity | technology | geography | supplier | customer | regulator | other
- Status: active | paused | archived
- Priority: 1-5
- Search keywords:
  - "keyword 1"
  - "keyword 2"
- Source priority:
  - investor relations
  - filings
  - earnings calls
  - Seeking Alpha
  - X
  - trade publications
  - research reports
- Connected entities:
  - <Other Entity>: <why connected, direction of influence, evidence>
- Last retrieval: YYYY-MM-DDTHH:MM:SSZ
- Last report: YYYY-MM-DD
- Notes: <short tracking rationale>
```

Rules:

- Keep connection explanations explicit. Do not list connected entities without explaining the economic, operational, technological, supply-chain, competitive, or narrative link.
- Keep search keywords narrow enough to retrieve relevant sources and broad enough to discover adjacent entities.
- Prefer stable names and ticker symbols where available.
- Preserve historical tracking context instead of rewriting it away.

### `data/entities.csv`

One row per entity. This is the spreadsheet-friendly overview file and should be importable into Google Sheets.

Required columns:

```csv
entity_id,slug,name,type,status,priority,ticker,exchange,currency,geography,sector,industry,business_lines,description,search_keywords,connected_entities,last_retrieval_at,last_report_date,last_source_count,confidence,owner_notes
```

### `data/relationships.csv`

One row per directed relationship.

Required columns:

```csv
source_slug,target_slug,relationship_type,direction,importance,mechanism,why_connected,evidence_url,last_reviewed_at,confidence
```

`relationship_type` examples: supplier, customer, competitor, substitute, demand_driver, cost_input, technology_dependency, regulatory_dependency, capital_market_proxy, macro_driver, person_affiliation.

### `data/estimates.csv`

One row per entity, business line, metric, and year. This is the main market-sizing and mispricing dataset.

Required columns:

```csv
entity_slug,entity_name,type,business_line,metric,unit,currency,actual_or_estimate,year,base_value,bearish_forecast,normal_forecast,bullish_forecast,bearish_thesis,normal_thesis,bullish_thesis,source_url,source_date,updated_at,confidence,notes
```

Supported metrics:

- revenue;
- EBITDA;
- EBIT;
- free cash flow;
- gross margin;
- operating margin;
- market size;
- market share;
- unit volume;
- ASP;
- capex;
- installed base;
- TAM/SAM/SOM;
- commodity price;
- production capacity.

### `source_log.csv`

Keep metadata, not full copyrighted articles.

Required columns:

```csv
source_id,entity_slug,title,source_name,source_type,url,author,published_at,retrieved_at,quality_score,recency_score,relevance_score,used_in_update,summary_path,hash,notes
```

Do not store complete article bodies. Store URLs, metadata, short summaries, and citations.

### `source_history.csv`

Deterministic source-state memory across daily runs.

Required columns:

```csv
history_key,source_id,entity_slug,title,source_name,source_type,url,first_seen_at,last_seen_at,last_selected_at,last_used_at,times_seen,times_selected,times_used,current_state,notes
```

Use this to avoid repeatedly treating the same source as new work.

### `source_registry.csv`

Systematic watchlist of recurring sources to scan.

Required columns:

```csv
source_id,platform,name,url,priority,entities,source_type,quality_notes,bias_notes,retrieval_frequency
```

Use this file for YouTube channels, Substacks, X accounts, and other recurring feeds/pages that should be checked on a schedule.

## Entity directory contract

Each tracked entity must have `entities/<entity_slug>/`.

### `wiki/`

Use llm-wiki style: structured, stable pages with incremental updates. Do not dump raw notes.

Minimum pages:

- `index.md` — overview, key facts, current thesis, source map;
- `business.md` — business model, segments, pricing power, unit economics;
- `market.md` — market size, growth, competitive landscape;
- `financials.md` — revenue, EBITDA, cash flow, balance sheet, valuation anchors;
- `technology.md` — technical moat, dependencies, bottlenecks;
- `people.md` — executives, founders, major shareholders, key public figures;
- `risks.md` — technical, regulatory, execution, market, financing, geopolitical risks;
- `sources.md` — curated source index and source quality notes.

### `thesis.md`

Maintain three explicit scenarios:

- bearish thesis;
- normal thesis;
- bullish thesis.

Each scenario must include:

- key assumptions;
- revenue and EBITDA path;
- market size path;
- business-line contribution;
- catalysts;
- disconfirming evidence;
- signposts to monitor.

### `financial_report.md`

Maintain a current report with:

- entity summary;
- business lines;
- latest financials;
- forecast table;
- valuation framing;
- market expectations;
- possible mispricing;
- major risks;
- connected-entity implications;
- open questions;
- source links.

### `daily_reports/report_YYYY-MM-DD.md`

Entity-specific daily report. Use uppercase `.MD` only if the existing repository convention uses uppercase; otherwise use lowercase `.md`. File names must use ISO dates.

## Daily workflow

A Hermes cron or scheduled skill run must execute this pipeline once per day.

### 1. Load registry

Use scripts to parse:

- `index.md`;
- `data/entities.csv`;
- each entity `source_log.csv`;
- `data/source_history.csv`;
- `data/source_registry.csv`;
- `data/daily_runs.csv`.

Determine `last_report_date` and `last_retrieval_at` for every active entity.

### 2. Retrieve candidate sources

For each active entity, retrieve candidate sources using its search keywords and connected entities.

Default source families:

- investor relations pages;
- SEC/EDGAR or local regulator filings where applicable;
- annual reports;
- quarterly reports;
- earnings-call transcripts;
- investor presentations;
- Seeking Alpha articles and deep dives;
- X posts and threads from high-signal accounts;
- trade publications;
- specialist research;
- company blogs;
- credible interviews;
- conference presentations;
- recurring sources listed in `data/source_registry.csv`.

Rules:

- Read maximum 10 new articles/items per entity since the last report time.
- Rank by quality first, then recency, then relevance.
- Prefer primary sources over commentary.
- Prefer long-form, data-rich, thesis-changing sources over short news items.
- Do not keep full article bodies after extraction.
- Keep source metadata and short summaries in `source_log.csv`.

Suggested deterministic ranking:

```text
final_score = quality_score * 0.45 + relevance_score * 0.35 + recency_score * 0.20
```

Quality-score guidance:

- 1.0: primary filings, official financial releases, official investor presentations;
- 0.9: earnings transcripts, management interviews, credible datasets;
- 0.8: specialist industry research, high-quality trade publications;
- 0.7: Seeking Alpha deep dives with clear financial model or primary-source references;
- 0.5: generic news;
- 0.3: unsourced X posts;
- 0.1: promotional or low-signal content.

### 3. Extract and classify

For every selected source, extract:

- entity/entities mentioned;
- business line affected;
- metric affected;
- forecast implication;
- thesis impact;
- related entities;
- source confidence;
- whether it updates wiki, thesis, CSV, financial report, or relationships.

### 4. Update wiki, thesis, CSV, and report

Use LLM reasoning for synthesis. Use scripts for CSV writes, validation, duplicate checks, link checks, date handling, and report rendering.

Update order:

1. entity wiki pages;
2. entity `thesis.md`;
3. entity `estimates.csv`;
4. global `data/estimates.csv`;
5. entity `financial_report.md`;
6. `data/relationships.csv`;
7. `index.md` connection notes;
8. daily reports.

### 5. Update synergies and connections

After entity updates, review relationships across all changed entities.

Look for:

- shared suppliers;
- shared customers;
- commodity dependencies;
- regulatory dependencies;
- technology platform dependencies;
- substitutive or complementary markets;
- shared demand drivers;
- capital-market narrative links;
- people links;
- geopolitical links.

Every new or changed relationship must include a `why_connected` explanation and an evidence URL.

### 6. Generate daily report

Use `python3 bin/worldmodel_generate_report.py --selected .worldmodel/selected.json` to build the deterministic report skeleton before any LLM-written thesis/fact narrative is added.

Generate one global file:

```text
reports/daily/report_YYYY-MM-DD.md
```

Also generate one per-entity file when that entity changed:

```text
entities/<entity_slug>/daily_reports/report_YYYY-MM-DD.md
```

Daily report must include:

- date and run ID;
- entities processed;
- sources read, with HTML source links;
- sources skipped and why;
- modified files with Markdown links;
- new facts;
- thesis changes;
- CSV changes;
- relationship changes;
- market mispricing/tendency signals;
- open questions;
- next retrieval hints.

### 7. Render GitHub Pages

Prepare Quartz content in `site/content/`, then build static HTML in `site/public/`.

Rules:

- preserve Markdown source links;
- generate Quartz content pages for entities, reports, relationships, and estimates;
- keep generated pages deterministic;
- do not manually edit `site/content/` or `site/public/`;
- keep repository Markdown and CSV files as the source of truth.

### 8. Maintenance

Run maintenance when scripts, templates, AGENTS.md, PLAN.md, or skills are inconsistent with observed workflow needs.

Maintenance tasks:

- validate CSV schemas;
- detect missing entity files;
- detect stale source logs;
- detect broken internal Markdown links;
- detect repeated sources;
- detect missing relationship explanations;
- detect missing bullish/normal/bearish forecast fields;
- propose changes to skills/scripts/templates;
- update docs when conventions change.

### 9. Commit and push

When the daily run produces changes:

```bash
git status --short
git add AGENTS.md PLAN.md index.md data templates entities reports skills bin docs
git commit -m "Update worldmodel daily report YYYY-MM-DD"
git push
```

For entity seeding:

```bash
git commit -m "Seed <entity> entity"
```

For maintenance:

```bash
git commit -m "Maintain worldmodel automation"
```

Remote target:

```text
https://github.com/Kabutojira/worldmodel
```

## Entity addition workflow

When a new entity is added:

1. create the entity entry in `index.md`;
2. add a row to `data/entities.csv`;
3. create `entities/<entity_slug>/` from templates;
4. search primary sources first:
   - investor relations;
   - filings;
   - annual reports;
   - quarterly reports;
   - investor presentations;
   - earnings-call transcripts;
   - official blogs or technical reports;
5. search in-depth external research;
6. seed wiki pages;
7. seed `thesis.md` with bearish/normal/bullish scenarios;
8. seed `financial_report.md`;
9. create initial estimates rows;
10. identify connected entities;
11. rank connected entities by importance;
12. recursively seed the most important connected entities when they materially affect the original thesis.

Do not recursively explode the graph. Add only entities with clear thesis impact.

## Initial entity: Tesla

Seed `Tesla` as the first company entity.

Suggested slug:

```text
tesla
```

Suggested type:

```text
company
```

Suggested search keywords:

- `Tesla investor relations`;
- `Tesla 10-K`;
- `Tesla 10-Q`;
- `Tesla earnings call transcript`;
- `Tesla vehicle deliveries`;
- `Tesla automotive gross margin`;
- `Tesla energy storage deployments`;
- `Tesla Megapack backlog`;
- `Tesla FSD robotaxi`;
- `Tesla Optimus humanoid robot`;
- `Tesla lithium supply`;
- `Tesla battery suppliers`.

Initial connected entities to consider:

- lithium — battery input cost and supply constraint;
- automotive market — core revenue pool and competitive benchmark;
- EV market — demand growth and adoption curve;
- battery storage market — Tesla Energy growth driver;
- autonomous driving / robotaxi — optionality and valuation narrative;
- humanoid robotics / Optimus — long-duration optionality;
- charging infrastructure — ecosystem moat and service revenue;
- Panasonic — historical battery supplier;
- CATL — battery supply and chemistry benchmark;
- LG Energy Solution — battery supply;
- BYD — EV competitor and battery competitor;
- Nvidia — AI compute dependency and autonomy benchmark;
- Elon Musk — key-person, governance, brand, and capital-market narrative link.

Each connected entity must be justified in `index.md` and `data/relationships.csv` before being tracked as active.

## Script rules

Write Python scripts for deterministic work:

- parsing `index.md`;
- validating CSV schemas;
- fetching source metadata;
- deduplicating URLs by canonical URL and content hash;
- scoring source recency;
- scoring source quality by configured source type;
- generating blank entity directories from templates;
- merging entity estimates into global CSV;
- rendering Markdown to HTML;
- checking links;
- creating commits.

Do not use LLMs for:

- CSV formatting;
- sorting;
- date parsing;
- schema validation;
- file discovery;
- duplicate detection;
- HTML rendering;
- Git operations.

Use LLMs for:

- source understanding;
- source relevance classification;
- thesis changes;
- relationship reasoning;
- market mispricing detection;
- entity discovery;
- report synthesis;
- maintenance recommendations.

## Source and copyright rules

- Do not store full copyrighted articles.
- Keep source URL, title, author, publication date, retrieval date, short summary, and extracted facts.
- Quote only short snippets when necessary.
- Prefer paraphrase with source link.
- Mark paywalled or access-limited sources in `source_log.csv`.
- Keep enough metadata to re-find the source later.

## Data-quality rules

Every non-obvious fact in a report must have a source URL.

Every estimate must include:

- source URL or explicit model note;
- scenario type;
- year;
- unit;
- confidence;
- updated date.

Every relationship must include:

- mechanism;
- why it matters;
- evidence URL;
- last reviewed date.

When evidence conflicts, preserve both views and mark uncertainty.

## Mispricing and tendency detection

Daily reports should explicitly identify possible market mispricing or emerging tendency signals.

Examples:

- market size growing faster than consensus narrative;
- margin pressure not reflected in valuation;
- supplier bottleneck not priced into dependent company;
- commodity cost trend improving or worsening unit economics;
- adjacent entity signal that changes another entity’s thesis;
- optionality narrative expanding without corresponding revenue evidence;
- earnings estimate revision risk.

Use cautious language. Separate evidence from inference.

## Maintenance triggers

Run maintenance when any of these occur:

- script failure;
- malformed CSV;
- missing required entity files;
- repeated source URLs;
- stale report date;
- relationship without explanation;
- estimates without scenario fields;
- daily report missing modified-file links;
- skill instructions diverge from actual repo layout;
- templates are missing fields used by scripts;
- Quartz/GitHub Pages render fails.

## Done criteria for a daily run

A daily run is complete only when:

- all active entities were checked or explicitly skipped with reason;
- maximum 10 selected new sources per entity were processed;
- source metadata was logged;
- wiki/thesis/CSV/report files were updated when needed;
- relationships were reviewed;
- daily reports were generated;
- Quartz content was prepared and GitHub Pages output was built;
- maintenance checks passed or maintenance issues were reported;
- changes were committed and pushed.
