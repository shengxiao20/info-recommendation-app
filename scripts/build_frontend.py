"""Assemble the HTML-only frontend. Does not read backend keys or SQLite data."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_frontend():
    html = (ROOT / 'frontend/template.html').read_text(encoding='utf-8')
    html = html.replace('/* INLINE_STYLES */', (ROOT / 'frontend/styles.css').read_text(encoding='utf-8'))
    html = html.replace('/* INLINE_APP */', (ROOT / 'frontend/app.js').read_text(encoding='utf-8'))
    target = ROOT / 'release/文章洞察-前端.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding='utf-8')
    print(f'Generated: {target} ({target.stat().st_size:,} bytes)')


if __name__ == '__main__':
    build_frontend()
