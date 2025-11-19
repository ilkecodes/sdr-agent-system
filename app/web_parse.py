"""Web page parser: fetch a URL (robots-checked), extract main article with Readability,
convert to Markdown, then call `app.convert.convert_file` to produce canonical markdown + chunks.

Usage:
  from app.web_parse import parse_url
  parse_url('https://example.com/article', out_dir='out', db_url=DATABASE_URL)
"""

from __future__ import annotations

import os
import hashlib
import logging
from typing import Optional

import requests
from urllib.parse import urlparse
from urllib import robotparser

try:
    from readability import Document
except Exception:
    Document = None

try:
    from markdownify import markdownify as mdify
except Exception:
    mdify = None

from sqlalchemy import create_engine, MetaData, Table, text

logger = logging.getLogger('web_parse')
logging.basicConfig(level=logging.INFO)


def _can_fetch(url: str, user_agent: str = 'rag-min-bot') -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots can't be read, default to allow
        return True


def parse_url(url: str, out_dir: str = 'out', db_url: Optional[str] = None, fetch: bool = True) -> dict:
    """Fetch URL, extract main article, convert to markdown, produce chunks via convert.convert_file,
    and optionally store full markdown in DB documents table.
    Returns dict with md_path and chunks_path.
    """
    if not Document or not mdify:
        raise RuntimeError('Missing dependencies: readability-lxml and markdownify are required')

    html = None
    # support local file paths when fetch is False
    if not fetch and os.path.exists(url):
        with open(url, 'r', encoding='utf-8') as fh:
            html = fh.read()
    else:
        if fetch and not _can_fetch(url):
            raise RuntimeError(f'Robots disallow fetching: {url}')

        headers = {'User-Agent': 'rag-min-bot/1.0'}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text

    doc = Document(html)
    title = doc.short_title() or doc.title() or url
    summary_html = doc.summary() or html

    # Convert to markdown
    md = mdify(summary_html, heading_style="ATX")

    # Save markdown to out_dir
    os.makedirs(out_dir, exist_ok=True)
    doc_stem = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
    md_path = os.path.join(out_dir, f"{doc_stem}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        # add minimal front matter
        f.write(f"# {title}\n\n")
        f.write(md)

    # Use convert.convert_file to produce canonical .md and chunks (convert will parse html if provided)
    from app.convert import convert_file
    # pass the sanitized article HTML as bytes and set source_uri to the canonical URL
    html_bytes = summary_html.encode('utf-8')
    res = convert_file(source_uri=url + '.html', file_bytes=html_bytes, mime='text/html', out_dir=out_dir)

    # Store full markdown in DB if requested
    if db_url:
        engine = create_engine(db_url)
        metadata = MetaData()
        docs_table = Table('documents', metadata, autoload_with=engine)
        md_full = open(res['md_path'], 'r', encoding='utf-8').read()
        meta = {
            'source_url': url,
            'title': title,
        }
        # Use checksum as doc_id
        doc_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
        with engine.begin() as conn:
            conn.execute(docs_table.insert().values(doc_id=doc_id, title=title, md=md_full, metadata=meta))

    return res


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Parse a web page into Markdown and chunks')
    p.add_argument('url')
    p.add_argument('--out', default='out')
    p.add_argument('--db', help='DATABASE_URL for storing full markdown')
    args = p.parse_args()
    print(parse_url(args.url, out_dir=args.out, db_url=args.db))
