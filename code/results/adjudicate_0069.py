"""Independent strict-path adjudication of preserved single-pass 0069 output."""
import csv, json, hashlib, re
from pathlib import Path
base=Path(__file__).resolve().parents[2]
expected={3:'d80069db26f2bc53914f58d73556ef283d216ffd513a71ea3aac5c1bf10bd83b',4:'9259a4092267a0bd8cfa23c40252f9e6f36c64bee05e8e32055c4ddf0b987c46',5:'8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07'}
def load(p):return [json.loads(s) for s in p.open(encoding='utf-8')]
def canon(p):
    p=p.replace('（只在台式机能打开）','').replace('\\','/')
    p=re.sub('/+','/',p)
    return p.casefold().replace('./','i:/')
def dump(p,rs):
    assert not p.exists(),p
    with p.open('w',encoding='utf-8') as f:
        for r in rs:f.write(json.dumps(r,ensure_ascii=False)+'\n')
def csvout(p,rs):
    assert not p.exists(),p
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
for n in (3,4,5):
    root=base/f'blind_round{n}';out=root/('results' if n==5 else 'rerun_0069')
    assert hashlib.sha256((root/'questions_blind.jsonl').read_bytes()).hexdigest()==expected[n]
    questions=load(root/'questions_blind.jsonl');raw=load(out/'results.jsonl')
    assert len(questions)==len(raw)==({3:30,4:12,5:30}[n])
    rows=[]
    for q,r in zip(questions,raw):
        assert q['id']==r['id'] and r['question_sha256']==expected[n] and r['exit_code']==0
        paths={canon(q['source_pdf'])}
        if n==5:paths.update(canon(v) for a in q.get('aliases',[]) for v in a.values())
        hits=r['hits'][:5]
        same=[h for h in hits if canon(h['source_pdf']) in paths]
        # In prior Zotero/EndNote blind sets, cross-library equivalence is in explicit result's same_work label.
        if n<5:same=[h for h in hits if h.get('same_work') or canon(h['source_pdf']) in paths]
        rows.append(dict(id=q['id'],group=q['group'],work_hit=bool(same),page_hit=any(isinstance(h.get('pdf_page'),int) and abs(h['pdf_page']-q['pdf_page'])<=1 for h in same),same_work_pages=[h['pdf_page'] for h in same],translation_fallback='本次未翻译' in r['raw_output'],internal_deadline='本次查询到了 60 秒上限' in r['raw_output'],desktop_source_path=any(('只在台式机能打开' in h['block']) and canon(h['source_pdf']).startswith('i:/') for h in same),candidate_title=any('题目候选' in h['heading'] for h in same),hex_title=any(re.match(r'^\d+\. <[0-9A-Fa-f]{20}',h['heading']) for h in same),ocr_warning=any('OCR 文本，引用前核原页' in h['block'] for h in same)))
    dump(out/'adjudicated_strict.jsonl',rows)
    groups=[]
    for group in list(dict.fromkeys(x['group'] for x in rows))+['ALL']:
        subset=[x for x in rows if x['group']==group or group=='ALL']
        groups.append(dict(group=group,n=len(subset),work_hit=sum(x['work_hit'] for x in subset),page_hit=sum(x['page_hit'] for x in subset),translation_fallback=sum(x['translation_fallback'] for x in subset),internal_deadline=sum(x['internal_deadline'] for x in subset)))
    csvout(out/'group_metrics_strict.csv',groups)
    prior=load(root/'rerun_0062/results.jsonl') if n<5 else []
    comparison=[]
    for i,row in enumerate(rows):
        old=prior[i] if prior else None
        if old:assert old['id']==row['id']
        change=('变好' if row['page_hit'] and not old['page_hit'] else '变差' if old['page_hit'] and not row['page_hit'] else '不变') if old else '首次，无前轮'
        comparison.append(dict(id=row['id'],group=row['group'],previous_page_hit=old['page_hit'] if old else None,current_page_hit=row['page_hit'],change=change,current_work_hit=row['work_hit'],same_work_pages=row['same_work_pages']))
    dump(out/'comparison_strict.jsonl',comparison)
    lines=[f'# 0069 round{n} 严格复核', '',f'冻结 SHA-256: `{expected[n]}`；一次正式调用，无补跑。只按前五条，同作品及 PDF 物理页 ±1；跨库同作品沿用 round3/4 的既有映射，round5 仅认冻结题的路径与别名，不以主题或文件名猜同作品。','', '| 组 | N | 作品 | 到页 | 翻译回退 | 内部截止 |','|---|---:|---:|---:|---:|---:|']
    lines += [f'| {g["group"]} | {g["n"]} | {g["work_hit"]} | {g["page_hit"]} | {g["translation_fallback"]} | {g["internal_deadline"]} |' for g in groups]
    lines += ['',f'与 0062 的逐题到页变化：变好 {sum(x["change"]=="变好" for x in comparison)}、变差 {sum(x["change"]=="变差" for x in comparison)}、不变 {sum(x["change"]=="不变" for x in comparison)}。' if n<5 else '首次轮次，没有前轮可比。']
    if n==5:
        same=[x for x in rows if x['work_hit']];oc=[x for x in same if x['group']=='ocr']
        lines += ['',f'正确作品召回 {len(same)} 题，其中台式机来源及 I: 路径标示 {sum(x["desktop_source_path"] for x in same)}/{len(same)}；“题目候选” {sum(x["candidate_title"] for x in same)}/{len(same)}，PDF Info 十六进制乱码题名 {sum(x["hex_title"] for x in same)}/{len(same)}。其余未据原书目核对，不自动算正式题名。OCR 正确作品召回 {len(oc)} 题，引用前核原页提示 {sum(x["ocr_warning"] for x in oc)}/{len(oc)}。', '30/30 中文问题均提示翻译失败并回退中文原文；英文来源两组 0/10 为此批调用的混杂结果，不能推断索引本身质量。R5-30 问句欠限定且错页，照原判不事后改题。', '原始结果的 R5-13 曾把 Zotero 另一本《Dynamics of Atmospheric Boundary Layer》误标同作品；原答案是台式机 JWEIA 的 90.pdf，严格路径裁决为未命中。故应采用此处的 adjudicated_strict.jsonl、group_metrics_strict.csv，不采用先前的 scored.jsonl 或 group_metrics.csv 作品命中数。']
    else:lines += ['', '服务内部 60 秒截止题的台式机/书籍路线可能没跑完；保留正式成绩，不私自重试。']
    lines += ['', '题目、答案和原始逐题片段只留在实验室，不交平台；平台可收到上述聚合与故障类型。','']
    p=out/'summary_strict.md';assert not p.exists(),p;p.write_text('\n'.join(lines),encoding='utf-8')
    print(n,groups)
