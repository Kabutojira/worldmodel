# WorldModel Site

## Purpose
The public site is generated from repository Markdown and CSV files.

## Local build

```bash
python3 bin/worldmodel_render_site.py --clean --strict
cd site
npm ci
npx quartz plugin install --from-config
npx quartz build
npx quartz build --serve
```

## GitHub Pages

The site is deployed by `.github/workflows/pages.yml` on every push to `main`.

## Source of truth

Do not manually edit `site/content/` or `site/public/`.

Edit root Markdown, `entities/`, `reports/`, and `data/` files instead.

## Graph

The graph is generated from `data/relationships.csv`, `index.md`, and Markdown links.
