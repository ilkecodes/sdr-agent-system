import os
import json
from app import convert


def test_convert_sample():
    src = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample.txt')
    src = os.path.normpath(src)
    out_dir = os.path.join(os.path.dirname(__file__), 'out')
    os.makedirs(out_dir, exist_ok=True)

    res = convert.convert_file(src, out_dir=out_dir)
    assert os.path.exists(res['md_path'])
    assert os.path.exists(res['chunks_path'])

    with open(res['chunks_path'], 'r', encoding='utf-8') as f:
        lines = [json.loads(l) for l in f if l.strip()]

    assert len(lines) > 0
    c = lines[0]
    # basic metadata checks
    assert 'chunk_id' in c
    assert 'text' in c
    assert 'summary' in c
    assert 'keywords' in c
    assert 'metadata' in c
    md = c['metadata']
    assert 'source_uri' in md
    assert 'checksum_sha256' in md
    assert 'tokens' in md

    # token size invariant (small sample should be small)
    assert md['tokens'] <= convert.TARGET_TOKENS * 1.05
