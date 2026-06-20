#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

from worldmodel_common import DOCS_DIR, ROOT, ensure_dir, html_escape


def convert_inline(text: str) -> str:
    text = html_escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href=""></a>', text)
    text = re.sub(r"`([^`]+)`", r'<code></code>', text)
    return text


def markdown_to_html(md: str, title: str) -> str:
    lines = md.splitlines()
    body = []
    in_list = False
    in_code = False
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith('```'):
            if in_code:
                body.append('</code></pre>')
                in_code = False
            else:
                body.append('<pre><code>')
                in_code = True
            continue
        if in_code:
            body.append(html_escape(stripped))
            continue
        if stripped.startswith('# '):
            if in_list:
                body.append('</ul>')
                in_list = False
            body.append(f'<h1>{convert_inline(stripped[2:])}</h1>')
        elif stripped.startswith('## '):
            if in_list:
                body.append('</ul>')
                in_list = False
            body.append(f'<h2>{convert_inline(stripped[3:])}</h2>')
        elif stripped.startswith('### '):
            if in_list:
                body.append('</ul>')
                in_list = False
            body.append(f'<h3>{convert_inline(stripped[4:])}</h3>')
        elif stripped.startswith('- '):
            if not in_list:
                body.append('<ul>')
                in_list = True
            body.append(f'<li>{convert_inline(stripped[2:])}</li>')
        elif not stripped:
            if in_list:
                body.append('</ul>')
                in_list = False
            body.append('')
        else:
            if in_list:
                body.append('</ul>')
                in_list = False
            body.append(f'<p>{convert_inline(stripped)}</p>')
    if in_list:
        body.append('</ul>')
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }}
    code, pre {{ background: #f4f4f4; }}
    code {{ padding: 0.1rem 0.25rem; }}
    pre {{ padding: 1rem; overflow-x: auto; }}
    a {{ color: #0645ad; }}
  </style>
</head>
<body>
{''.join(part + '\n' for part in body)}
</body>
</html>
"""


def render_one(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    dst.write_text(markdown_to_html(src.read_text(encoding='utf-8'), src.stem), encoding='utf-8')


def main() -> int:
    ensure_dir(DOCS_DIR)
    for md in sorted(ROOT.rglob('*.md')):
        if md.is_relative_to(DOCS_DIR):
            continue
        rel = md.relative_to(ROOT)
        out = DOCS_DIR / rel.with_suffix('.html')
        render_one(md, out)
    index = DOCS_DIR / 'index.html'
    if not index.exists() and (ROOT / 'index.md').exists():
        render_one(ROOT / 'index.md', index)
    print(f"rendered site under {DOCS_DIR}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
