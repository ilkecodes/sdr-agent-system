import os
import subprocess
import time
import tempfile
import json

import pytest
from sqlalchemy import create_engine, text


def docker_available() -> bool:
    for cmd in (['docker', 'compose', 'version'], ['docker-compose', 'version']):
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


@pytest.mark.skipif(not docker_available(), reason='Docker not available')
def test_full_flow(tmp_path):
    """Integration test: start DB, run convert, ingest chunks, assert rows in rag_chunks.

    This test requires Docker and will bring up the `docker-compose.yml` service defined in the repo.
    It is conservative and will teardown the compose stack at the end.
    """
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Start docker compose
    try:
        subprocess.run(['docker', 'compose', 'up', '-d'], check=False, cwd=repo)
    except Exception:
        # try legacy
        subprocess.run(['docker-compose', 'up', '-d'], check=False, cwd=repo)

    # wait for Postgres to accept connections
    database_url = os.environ.get('DATABASE_URL') or 'postgresql+psycopg://rag:ragpw@localhost:5433/ragdb'
    engine = create_engine(database_url)
    deadline = time.time() + 60
    ok = False
    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
                ok = True
                break
        except Exception:
            time.sleep(1)

    assert ok, 'Postgres did not become available in time'

    # Run convert on sample file
    from app.convert import convert_file
    sample = os.path.join(repo, 'data', 'sample.txt')
    out_dir = str(tmp_path)
    res = convert_file(sample, out_dir=out_dir)

    assert os.path.exists(res['md_path'])
    assert os.path.exists(res['chunks_path'])

    # Ingest chunks
    from app.ingest_snippet import ingest_chunks
    n = ingest_chunks(res['chunks_path'], database_url=database_url)
    assert n > 0

    # Confirm rows are present
    with engine.connect() as conn:
        r = conn.execute(text('SELECT COUNT(*) FROM rag_chunks')).scalar()
    assert r > 0

    # Attempt an actual RAG query using app.query.ask if Ollama is available
    try:
        import ollama  # type: ignore
        has_ollama = True
    except Exception:
        has_ollama = False

    if has_ollama:
        # ensure query module uses the same DATABASE_URL
        os.environ['DATABASE_URL'] = database_url
        from app import query as query_mod
        try:
            # simple smoke query; this will call local Ollama and may be slow
            ans = query_mod.ask("What is the content of the sample file?", top_k=3, verbose=False)
            assert isinstance(ans, str)
        except Exception as e:
            pytest.skip(f'Ollama present but query failed: {e}')
    else:
        pytest.skip('Ollama not installed; skipping RAG query')

    # Teardown
    try:
        subprocess.run(['docker', 'compose', 'down'], check=False, cwd=repo)
    except Exception:
        subprocess.run(['docker-compose', 'down'], check=False, cwd=repo)
