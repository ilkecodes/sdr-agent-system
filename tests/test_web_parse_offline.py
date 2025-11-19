import os
from app.web_parse import parse_url


def test_web_parse_offline(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    fixture = os.path.join(repo, 'tests', 'fixtures', 'sample_article.html')
    out_dir = str(tmp_path)

    res = parse_url(fixture, out_dir=out_dir, db_url=None, fetch=False)

    assert os.path.exists(res['md_path'])
    assert os.path.exists(res['chunks_path'])

    # The produced markdown should contain the H1 heading
    md = open(res['md_path'], 'r', encoding='utf-8').read()
    assert 'Sample Article Heading' in md
