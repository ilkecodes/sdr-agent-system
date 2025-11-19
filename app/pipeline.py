"""Orchestration for the RAG pipeline: convert -> ingest -> validate -> optional query

Usage:
  python -m app.pipeline /path/to/doc.pdf --out out --ingest --query

The module uses `app.convert.convert_file` and `app.ingest_snippet.ingest_chunks`.
It will skip parts if dependencies or services are not available (e.g., Ollama).
"""

from __future__ import annotations

import os
import sys
import argparse
import logging

from typing import Optional

logger = logging.getLogger('pipeline')
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_convert(source: str, out_dir: Optional[str] = None):
    from app.convert import convert_file
    logger.info('Converting %s', source)
    res = convert_file(source, out_dir=out_dir)
    logger.info('Wrote markdown: %s', res['md_path'])
    logger.info('Wrote chunks:   %s', res['chunks_path'])
    return res


def run_ingest(chunks_path: str, database_url: Optional[str] = None):
    try:
        from app.ingest_snippet import ingest_chunks
    except Exception as e:
        logger.error('Ingest helper not available: %s', e)
        raise

    logger.info('Ingesting chunks into DB')
    n = ingest_chunks(chunks_path, database_url=database_url)
    logger.info('Inserted %d rows', n)
    return n


def run_query(question: str, top_k: int = 5):
    try:
        from app import query as query_mod
    except Exception as e:
        logger.error('Query module not available: %s', e)
        raise

    # set verbose True to see interactive prints
    logger.info('Running query: %s', question)
    ans = query_mod.ask(question, top_k=top_k, verbose=True)
    logger.info('Query returned type: %s', type(ans))
    return ans


def main(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser(description='RAG pipeline orchestration')
    p.add_argument('source', nargs='?', help='path to source file')
    p.add_argument('--url', help='URL to fetch and parse (web parser)')
    p.add_argument('--out', help='output directory for markdown and chunks', default='out')
    p.add_argument('--ingest', help='also ingest chunks into DB', action='store_true')
    p.add_argument('--db', help='DATABASE_URL for ingestion', default=os.environ.get('DATABASE_URL'))
    p.add_argument('--query', help='run a sample query after ingest', action='store_true')
    p.add_argument('--question', help='question to ask when --query is set', default='Summarize the document')
    p.add_argument('--top-k', help='top_k for retrieval', type=int, default=5)

    args = p.parse_args(argv)

    res = None
    # If a URL is provided, use the web parser
    if args.url:
        from app.web_parse import parse_url
        logger.info('Parsing URL %s', args.url)
        res = parse_url(args.url, out_dir=args.out, db_url=args.db, fetch=True)
    elif args.source:
        res = run_convert(args.source, out_dir=args.out)
    else:
        logger.error('Either SOURCE or --url must be provided')
        sys.exit(2)

    if args.ingest:
        if not args.db:
            logger.error('DATABASE_URL is required for ingest. Set via --db or DATABASE_URL env var.')
            sys.exit(2)
        run_ingest(res['chunks_path'], database_url=args.db)

    if args.query:
        try:
            run_query(args.question, top_k=args.top_k)
        except Exception as e:
            logger.warning('Query failed or Ollama not available: %s', e)


if __name__ == '__main__':
    main()
