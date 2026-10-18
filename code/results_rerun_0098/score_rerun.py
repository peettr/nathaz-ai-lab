import collections, hashlib, json, pathlib, re
base=pathlib.Path(__file__).resolve().parent
root=base.parent
questions=root/'questions_blind.jsonl'
expect='8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07'
assert hashlib.sha256(questions.read_bytes()).hexdigest()==expect
q=[json.loads(s) for s in questions.read_text().splitlines()]
r=[json.loads(s) for s in (base/'results.jsonl').read_text().splitlines()]
old=[json.loads(s) for s in (root/'results/scored.jsonl').read_text().splitlines()]
assert len(q)==len(r)==len(old)==30 and [x['id'] for x in q]==[x['id'] for x in r]==[x['id'] for x in old]
assert all(x['question_sha256']==expect and x['exit_code']==0 and x['elapsed_s']<90 for x in r)
def canonical(p):
    return p.replace('（只在台式机能打开）','').replace('\\','/').replace('./','I:/').casefold()
rows=[]
for x,y,z in zip(q,r,old):
    paths={canonical(p) for p in [x['source_pdf'],*(v for a in x.get('aliases',[]) for v in a.values())]}
    top=[h for h in y['hits'] if h['rank']<=5]
    same=[h for h in top if canonical(h['source_pdf']) in paths]
    page=[h for h in same if abs(h['pdf_page']-x['pdf_page'])<=1]
    rows.append(dict(id=x['id'],group=x['group'],expected_page=x['pdf_page'],work_hit=bool(same),page_hit=bool(page),same_work_pages=[h['pdf_page'] for h in same],old_work_hit=z['work_hit'],old_page_hit=z['page_hit'],change='变好' if bool(page) and not z['page_hit'] else '变差' if z['page_hit'] and not page else '不变',translation_failed='本次未翻译' in y['raw_output'],translated='已译成英文检索' in y['raw_output'],search_cap='本次查询到了 60 秒上限' in y['raw_output'],desktop_incomplete='没跑完的部分：台式机来源' in y['raw_output'],any_desktop=any('只在台式机能打开' in h['block'] for h in top),any_candidate=any('题目候选' in h['heading'] for h in top),any_table=any('疑似表格' in h['heading'] for h in top),elapsed_s=y['elapsed_s']))
(base/'scored.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in rows))
print('GROUP',dict((g,(sum(t['page_hit'] for t in rows if t['group']==g),sum(t['group']==g for t in rows),sum(t['work_hit'] for t in rows if t['group']==g))) for g in sorted({t['group'] for t in rows})))
print('FLAGS',dict((k,sum(t[k] for t in rows)) for k in ['translated','translation_failed','search_cap','desktop_incomplete','any_desktop','any_candidate','any_table']))
print('CHANGES',dict(collections.Counter(t['change'] for t in rows)))
print('ROWS',[(t['id'],t['page_hit'],t['work_hit'],t['same_work_pages'],t['change']) for t in rows])
print('ELAPSED',sum(t['elapsed_s'] for t in rows))
