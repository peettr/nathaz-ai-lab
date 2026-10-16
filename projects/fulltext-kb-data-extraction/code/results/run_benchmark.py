import argparse, hashlib, json, pathlib, re, subprocess, time, unicodedata

p = argparse.ArgumentParser()
p.add_argument('questions', type=pathlib.Path)
p.add_argument('dest', type=pathlib.Path)
p.add_argument('sha256')
p.add_argument('ctx')
a = p.parse_args()
assert hashlib.sha256(a.questions.read_bytes()).hexdigest() == a.sha256, 'frozen SHA mismatch'
items = [json.loads(s) for s in a.questions.read_text().splitlines()]
assert len({x['id'] for x in items}) == len(items)
a.dest.parent.mkdir(parents=True, exist_ok=True)
completed = {json.loads(s)['id'] for s in a.dest.read_text().splitlines()} if a.dest.exists() else set()

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC', s).casefold() if c.isalnum())

def parse(raw, x):
    hits = []
    for block in re.split(r'(?m)^\s*(?=[1-6]\. )', raw):
        match = re.match(r'\s*([1-6])\. .*?PDF 第\s*(\d+)\s*页', block)
        if not match:
            continue
        key = re.search(r'(?:Zotero|EndNote) 条目\s+([^\s/；]+)', block)
        pdf = re.search(r'(?m)^\s*PDF：([^\n]+)', block)
        heading = block.splitlines()[0].strip()
        h = dict(rank=int(match[1]), pdf_page=int(match[2]), key=key[1] if key else '', source_pdf=pdf[1].strip() if pdf else '', heading=heading)
        if 'sha256' in x:
            # A different path can hold the same work. Exact full-title/alias match is provisional and audited later.
            names = [x['title']]
            paths = [x['source_pdf'], *(v for alias in x.get('aliases', []) for v in alias.values())]
            same = bool(h['source_pdf'] in paths or any(norm(n) and norm(n) in norm(heading) for n in names))
        else:
            same = bool(h['source_pdf'] == x['source_pdf'] or (h['key'] and h['key'] == x['source_key']) or (not x['ocr'] and norm(x['title']) and norm(x['title']) in norm(heading)))
        h['same_work'] = same
        h['page_hit'] = same and abs(h['pdf_page'] - x['pdf_page']) <= 1
        # Store block privately to audit 0069 source/title/table metadata without modifying original output.
        h['block'] = block
        hits.append(h)
    return hits

with a.dest.open('a') as f:
    for x in items:
        if x['id'] in completed:
            continue
        start = time.monotonic()
        try:
            run = subprocess.run(['rc-kb', '--ctx', a.ctx, 'pages', x['question'], '-n', '5'], capture_output=True, text=True, timeout=90)
            raw, err, code = run.stdout, run.stderr, run.returncode
        except subprocess.TimeoutExpired as exc:
            raw = exc.stdout.decode(errors='replace') if isinstance(exc.stdout, bytes) else exc.stdout or ''
            err = exc.stderr.decode(errors='replace') if isinstance(exc.stderr, bytes) else exc.stderr or 'timeout'
            code = 124
        hits = parse(raw, x)
        obj = dict(id=x['id'], group=x['group'], question=x['question'], question_sha256=a.sha256, expected_pdf_page=x['pdf_page'], exit_code=code, elapsed_s=round(time.monotonic()-start, 2), hits=hits, work_hit=any(h['same_work'] for h in hits if h['rank'] <= 5), page_hit=any(h['page_hit'] for h in hits if h['rank'] <= 5), raw_output=raw, stderr=err)
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        f.flush()
        print(x['id'], len(hits), obj['page_hit'], obj['work_hit'], obj['elapsed_s'], flush=True)
