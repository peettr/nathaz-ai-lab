import collections, hashlib, json, pathlib, re, statistics, unicodedata
base=pathlib.Path(__file__).resolve().parents[2]

def load(path):
    return [json.loads(s) for s in path.read_text().splitlines()]
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(s)).casefold() if c.isalnum())
def canonical(p):
    return p.replace('（只在台式机能打开）','').replace('\\','/').replace('./','I:/').casefold()
def evaluate(n):
    root=base/f'blind_round{n}'
    qs=load(root/'questions_blind.jsonl'); rs=load(root/('results/results.jsonl' if n==5 else 'rerun_0069/results.jsonl'))
    assert len(qs)==len(rs)==({3:30,4:12,5:30}[n]); assert [q['id'] for q in qs]==[r['id'] for r in rs]
    assert all(r['exit_code']==0 and r['question_sha256']==hashlib.sha256((root/'questions_blind.jsonl').read_bytes()).hexdigest() for r in rs)
    rows=[]
    for q,r in zip(qs,rs):
        expected_paths=[q['source_pdf']]
        if n==5: expected_paths += [v for a in q.get('aliases',[]) for v in a.values()]
        for h in r['hits']:
            if n==5:
                h['same_work']=canonical(h['source_pdf']) in {canonical(p) for p in expected_paths}
                # Never infer same-work merely from abbreviated filenames/subject.
            else:
                h['same_work']=h['same_work'] or canonical(h['source_pdf'])==canonical(q['source_pdf'])
            h['page_hit']=h['same_work'] and abs(h['pdf_page']-q['pdf_page'])<=1
        top=[h for h in r['hits'] if h['rank']<=5]
        row=dict(id=q['id'],group=q['group'],work_hit=any(h['same_work'] for h in top),page_hit=any(h['page_hit'] for h in top),expected_page=q['pdf_page'],same_work_pages=[h['pdf_page'] for h in top if h['same_work']],top1_desktop='只在台式机能打开' in top[0]['block'] if top else False,top1_candidate='题目候选' in top[0]['heading'] if top else False,top1_table='疑似表格' in top[0]['heading'] if top else False,any_desktop=any('只在台式机能打开' in h['block'] for h in top),any_candidate=any('题目候选' in h['heading'] for h in top),any_table=any('疑似表格' in h['heading'] for h in top),translation_failed='本次未翻译' in r['raw_output'],elapsed_s=r['elapsed_s'])
        rows.append(row)
    dest=root/('results' if n==5 else 'rerun_0069')/'scored.jsonl'
    dest.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
    print('ROUND',n,'counts',collections.Counter((r['group'],r['work_hit'],r['page_hit']) for r in rows),'elapsed',sum(r['elapsed_s'] for r in rows),'flags',collections.Counter(k for r in rows for k in ('top1_desktop','top1_candidate','top1_table','any_desktop','any_candidate','any_table') if r[k]))
    print('FAILS',[(r['id'],r['same_work_pages']) for r in rows if not r['page_hit']])
    return rows

allrows={n:evaluate(n) for n in (3,4,5)}
for n in (3,4):
    root=base/f'blind_round{n}'
    rows=allrows[n]
    hist={
        '三期': load(base/'blind_round3_p3/adjudicated_results.jsonl') if n==3 else None,
        '0057': load(base/'blind_round3_p4/adjudicated_results.jsonl') if n==3 else load(root/'results.jsonl'),
        '0062': load(root/'rerun_0062/results.jsonl')}
    # R3 original 0060 run and R4 0060 run kept separately.
    if n==3: hist['初测']=load(root/'adjudicated_results.jsonl')
    snapshots={name:{x['id']:x for x in old} for name,old in hist.items() if old is not None}
    comparisons=[]
    for row in rows:
        item={'id':row['id'],'group':row['group'],'0069_work_hit':row['work_hit'],'0069_page_hit':row['page_hit'],'0069_same_work_pages':row['same_work_pages']}
        for name,old in snapshots.items():
            previous=old[row['id']]
            item[name+'_work_hit']=previous['work_hit']
            item[name+'_page_hit']=previous['page_hit']
            item[name+'_change']='变好' if row['page_hit'] and not previous['page_hit'] else '变差' if previous['page_hit'] and not row['page_hit'] else '不变'
        comparisons.append(item)
    dest=root/'rerun_0069/comparison.jsonl'
    dest.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in comparisons))
    print('NOW',n,'page',sum(r['page_hit'] for r in rows),'work',sum(r['work_hit'] for r in rows))
    for name in snapshots:
        print('COMPARE',n,name,collections.Counter(x[name+'_change'] for x in comparisons))
