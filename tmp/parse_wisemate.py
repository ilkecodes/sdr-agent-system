from app.web_parse import parse_url
import traceback, json

url='https://www.linkedin.com/company/wisemate/about/'
try:
    res = parse_url(url, out_dir='out', db_url=None, fetch=True)
    print('PARSE_RESULT:', res)
    md_path=res.get('md_path')
    chunks_path=res.get('chunks_path')
    if md_path:
        with open(md_path,'r',encoding='utf-8') as f:
            md=f.read()
        print('\n---MD_START---')
        print(md)
        print('---MD_END---\n')
    if chunks_path:
        with open(chunks_path,'r',encoding='utf-8') as fh:
            first=fh.readline()
        print('---FIRST_CHUNK_JSONL---')
        print(first)
except Exception as e:
    print('ERROR',e)
    traceback.print_exc()
