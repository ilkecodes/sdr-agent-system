"""Ingestion helper: read chunks JSONL and insert into `rag_chunks` table.

This helper computes embeddings with SentenceTransformers (model default: all-MiniLM-L6-v2)
and inserts rows grouped by document checksum (used as doc_id). It expects a running
Postgres+pgvector instance and a SQLAlchemy-compatible DATABASE_URL.

Note: this is a best-effort helper for the demo repository. It casts embedding vectors
to Postgres `vector` by passing a string literal like '[0.1, 0.2, ...]' and using `::vector` in SQL.
If your environment uses a different adapter, adjust accordingly (e.g., use pgvector SQLAlchemy type).
"""

from __future__ import annotations

import os
import json
from typing import Optional
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.postgresql import JSONB
from sentence_transformers import SentenceTransformer
from pgvector.sqlalchemy import Vector
import time
import os
import re

# optional imports
try:
    import tiktoken
except Exception:
    tiktoken = None

try:
    from langdetect import detect as lang_detect
except Exception:
    lang_detect = None


def ingest_chunks(chunks_jsonl_path: str, database_url: Optional[str] = None, model_name: str = 'all-MiniLM-L6-v2') -> int:
    """Read chunks JSONL and insert into rag_chunks.

    Returns number of rows inserted.
    """
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL')
    assert database_url, 'DATABASE_URL required (env or param)'

    engine = create_engine(database_url)

    # Load embedding model
    model = SentenceTransformer(model_name)
    # expected embedding dimension (use env to be explicit); default to 384 for local model
    expected_dim = int(os.environ.get('EXPECTED_EMBED_DIM', '384'))

    inserted = 0
    # Read and group chunks by document id (checksum)
    with open(chunks_jsonl_path, 'r', encoding='utf-8') as f:
        docs = {}
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            meta = obj.get('metadata', {})
            doc_id = meta.get('checksum_sha256') or meta.get('source_uri') or 'unknown'
            docs.setdefault(doc_id, []).append((obj, meta))

    metadata = MetaData()
    # reflect existing table (must exist)
    chunks_table = Table('rag_chunks', metadata, autoload_with=engine)

    with engine.begin() as conn:
        for doc_id, items in docs.items():
            for idx, (obj, meta) in enumerate(items, start=1):
                text_content = obj.get('text', '')
                # Pre-embedding QA: language detection (optional), token length, PII heuristic
                qa = {}
                if lang_detect:
                    try:
                        qa['language'] = lang_detect(text_content)
                    except Exception:
                        qa['language'] = None

                # token count estimate: prefer tiktoken if available
                token_count = None
                if tiktoken:
                    try:
                        enc = tiktoken.get_encoding('cl100k_base')
                        token_count = len(enc.encode(text_content))
                    except Exception:
                        token_count = None
                if token_count is None:
                    token_count = max(1, len(text_content.split()))
                qa['token_count'] = token_count

                # simple PII heuristics
                pii_types = []
                if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text_content):
                    pii_types.append('email')
                if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text_content):
                    pii_types.append('ssn')
                if re.search(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b', text_content):
                    pii_types.append('credit_card')
                qa['pii_types'] = pii_types

                # compute embedding
                emb = model.encode([text_content], show_progress_bar=False)[0].tolist()

                # embedding-dimension guard
                if expected_dim and len(emb) != expected_dim:
                    raise RuntimeError(
                        f'Embedding dimension mismatch: model produced {len(emb)} dims but EXPECTED_EMBED_DIM={expected_dim}. '
                        'Set EXPECTED_EMBED_DIM env or change DB schema/mode.'
                    )

                # build metadata: merge existing and ingestion info
                new_meta = {**meta}
                new_meta.update({
                    'ingested_at': int(time.time()),
                    'embedding_model': model_name,
                    'embedding_dim': len(emb),
                    'qa': qa,
                })

                insert_stmt = pg_insert(chunks_table).values(
                    doc_id=doc_id,
                    chunk_id=idx,
                    content=text_content,
                    metadata=new_meta,
                    embedding=emb,
                ).on_conflict_do_nothing(index_elements=['doc_id', 'chunk_id'])

                conn.execute(insert_stmt)
                inserted += 1

    return inserted


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Ingest chunks JSONL into rag_chunks')
    p.add_argument('chunks', help='path to chunks.jsonl')
    p.add_argument('--db', help='SQLAlchemy DATABASE_URL (optional, env DATABASE_URL used otherwise)')
    p.add_argument('--model', help='sentence-transformers model', default='all-MiniLM-L6-v2')
    args = p.parse_args()
    n = ingest_chunks(args.chunks, database_url=args.db, model_name=args.model)
    print(f'Inserted {n} rows')
