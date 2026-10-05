from concurrent.futures import ThreadPoolExecutor
from pipeline.vlm_parse import parse_page
M="openrouter:google/gemini-3.1-pro-preview"
def run(p):
    try:
        parse_page(p, M, prompt="page_parse.v1"); return p,"ok"
    except Exception as e: return p,repr(e)[:200]
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(run,[12,14,16,18,22,24,26,28,33,35,37,39]): print(r, flush=True)
