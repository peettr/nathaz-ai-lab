import csv, hashlib, json, os, pathlib, re, subprocess, time, collections, datetime
ROOT = pathlib.Path(__file__).parent
CTX = os.environ['RC_CTX']
DUPLICATE = {'END-5c6650f021459749': './Zotero/storage/HUZ2C9E3/台风风场模型研究综述.pdf'}

def norm(s):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '', s.lower())

def parse(raw, q):
    blocks = re.split(r'(?m)^\s*(?=[1-9]\. )', raw)
    hits = []
    for b in blocks:
        m = re.match(r'\s*([1-9])\. .*?PDF 第\s*(\d+)\s*页', b)
        if not m or int(m[1]) > 5:
            continue
        k = re.search(r'(?:Zotero|EndNote) 条目\s+([^\s/；]+)', b)
        pdf = re.search(r'(?m)^\s*PDF：([^\n]+)', b)
        heading = b.splitlines()[0].strip()
        path = pdf[1].strip() if pdf else ''
        key = k[1] if k else ''
        alias = '同一作品另有' in b and q['source_key'] in b.split('卡片：')[0]
        same = bool(path == q['source_pdf'] or key == q['source_key'] or path == DUPLICATE.get(q['source_key']) or alias or (not q['ocr'] and norm(q['title']) and norm(q['title']) in norm(heading)))
        hits.append({'rank': int(m[1]), 'pdf_page': int(m[2]), 'key': key, 'source_pdf': path, 'heading': heading, 'same_work': same, 'page_hit': same and abs(int(m[2]) - q['pdf_page']) <= 1})
    return hits

for roundno, expected, n in ((3, 'd80069db26f2bc53914f58d73556ef283d216ffd513a71ea3aac5c1bf10bd83b', 30), (4, '9259a4092267a0bd8cfa23c40252f9e6f36c64bee05e8e32055c4ddf0b987c46', 12)):
    base = ROOT / f'blind_round{roundno}'
    qfile = base / 'questions_blind.jsonl'
    assert hashlib.sha256(qfile.read_bytes()).hexdigest() == expected
    questions = [json.loads(line) for line in qfile.read_text().splitlines()]
    assert len(questions) == n and len({q['id'] for q in questions}) == n
    oldfile = base / ('adjudicated_results.jsonl' if roundno == 3 else 'results.jsonl')
    old = {x['id']: x for x in map(json.loads, oldfile.read_text().splitlines())}
    assert set(old) == {q['id'] for q in questions}
    dest = base / 'rerun_0062'
    dest.mkdir(exist_ok=True)
    outfile = dest / 'results.jsonl'
    if outfile.exists():
        done = [json.loads(s) for s in outfile.read_text().splitlines()]
        assert len(done) == len({x['id'] for x in done})
        assert all(x['question_sha256'] == expected for x in done)
        doneids = {x['id'] for x in done}
    else:
        doneids = set()
    with outfile.open('a') as f:
        for q in questions:
            if q['id'] in doneids:
                continue
            t = time.monotonic()
            try:
                p = subprocess.run(['rc-kb', '--ctx', CTX, 'pages', q['question'], '-n', '5'], capture_output=True, text=True, timeout=180)
                raw, err, code = p.stdout, p.stderr, p.returncode
            except subprocess.TimeoutExpired as e:
                raw = (e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
                err, code = 'timeout', 124
            hits = parse(raw, q)
            row = {'id': q['id'], 'group': q['group'], 'question': q['question'], 'question_sha256': expected, 'expected_key': q['source_key'], 'expected_pdf_page': q['pdf_page'], 'exit_code': code, 'elapsed_s': round(time.monotonic()-t, 2), 'hits': hits, 'work_hit': any(h['same_work'] for h in hits), 'page_hit': any(h['page_hit'] for h in hits), 'raw_output': raw, 'stderr': err}
            f.write(json.dumps(row, ensure_ascii=False)+'\n')
            f.flush()
            print(q['id'], 'code',code,'hits',len(hits),'page',row['page_hit'],'work',row['work_hit'], flush=True)
    rows = [json.loads(s) for s in outfile.read_text().splitlines()]
    assert len(rows) == n and {x['id'] for x in rows} == set(old)
    # Keep the raw formal call intact; score strictly on the first five returned pages.
    groups = sorted({x['group'] for x in rows}) + ['all']
    with (dest/'group_metrics.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['group','n','before_work_at_5','after_work_at_5','before_page_pm1_at_5','after_page_pm1_at_5','page_better','page_worse','page_unchanged'])
        for g in groups:
            sub=[x for x in rows if x['group']==g or g=='all']
            before=[old[x['id']] for x in sub]
            w.writerow([g,len(sub),sum(x['work_hit'] for x in before),sum(x['work_hit'] for x in sub),sum(x['page_hit'] for x in before),sum(x['page_hit'] for x in sub),sum(not a['page_hit'] and b['page_hit'] for a,b in zip(before,sub)),sum(a['page_hit'] and not b['page_hit'] for a,b in zip(before,sub)),sum(a['page_hit']==b['page_hit'] for a,b in zip(before,sub))])
    comp=[]
    for x in rows:
        prev=old[x['id']]; shift=('变好' if x['page_hit'] and not prev['page_hit'] else '变差' if prev['page_hit'] and not x['page_hit'] else '不变')
        reason=('命中' if x['page_hit'] else '页错' if x['work_hit'] else '未召回')
        comp.append({'id':x['id'],'group':x['group'],'before_work_hit':prev['work_hit'],'after_work_hit':x['work_hit'],'before_page_hit':prev['page_hit'],'after_page_hit':x['page_hit'],'page_change':shift,'reason':reason,'returned_work_pages':[h['pdf_page'] for h in x['hits'] if h['same_work']]})
    (dest/'comparison.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in comp))
    metric=(dest/'group_metrics.csv').read_text()
    failures=[x for x in comp if not x['after_page_hit']]
    lines=[f'# 平台 0062 上线后盲测复跑：round {roundno}', '', f'本轮题库 SHA-256 `{expected}`；{n} 题各调用 rc-kb pages -n 5 一次，不修改冻结题库。严格按前五唯一作品/物理页 ±1；同作品跨库副本计入。题目、答案和原始输出仅留实验室，不发平台。', '', '## 分组（作品命中、到页命中均为前五）', '', '```csv',metric.strip(),'```', '', '## 未到页题与逐题变化', '', '```text']
    lines += [f"{x['id']} {x['group']} {x['page_change']} {x['reason']} 同作品返回页={x['returned_work_pages']}" for x in failures]
    lines += ['```','','逐题变好/变差/不变详见 `comparison.jsonl`，原始输出详见 `results.jsonl`。失败的 OCR/翻译原因仅是候选解释；没有原页 OCR 复查及翻译诊断，不将未召回直接归为 OCR 或翻译错。无外送全文；0 CU。','']
    (dest/'summary.md').write_text('\n'.join(lines))
    print('FINISHED', roundno, metric, flush=True)
