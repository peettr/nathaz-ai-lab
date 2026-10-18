"""Aggregate preserved one-pass rc-kb 0069 blind results; no service calls."""
import collections
import csv
import hashlib
import json
from pathlib import Path

base = Path(__file__).resolve().parents[2]
expected_hash = {3:'d80069db26f2bc53914f58d73556ef283d216ffd513a71ea3aac5c1bf10bd83b',4:'9259a4092267a0bd8cfa23c40252f9e6f36c64bee05e8e32055c4ddf0b987c46',5:'8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07'}

def load(path):
    return [json.loads(line) for line in path.open(encoding='utf-8')]

def write_csv(path,rows):
    assert not path.exists(), f'Will not overwrite {path}'
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def write_jsonl(path,rows):
    assert not path.exists(), f'Will not overwrite {path}'
    with path.open('w',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')

def write_md(path,txt):
    assert not path.exists(), f'Will not overwrite {path}'
    path.write_text(txt,encoding='utf-8')

for n in (3,4,5):
    root=base/f'blind_round{n}'
    out=root/('results' if n==5 else 'rerun_0069')
    assert hashlib.sha256((root/'questions_blind.jsonl').read_bytes()).hexdigest()==expected_hash[n]
    qs=load(root/'questions_blind.jsonl'); raw=load(out/'results.jsonl'); scored=load(out/'scored.jsonl')
    assert len(qs)==len(raw)==len(scored)==({3:30,4:12,5:30}[n])
    assert [q['id'] for q in qs]==[r['id'] for r in raw]==[s['id'] for s in scored]
    assert len(set(s['id'] for s in scored))==len(scored)
    assert all(r['exit_code']==0 and r['question_sha256']==expected_hash[n] for r in raw)
    group_rows=[]
    for group in dict.fromkeys(s['group'] for s in scored):
        rows=[s for s in scored if s['group']==group]
        group_rows.append(dict(group=group,n=len(rows),work_hit=sum(s['work_hit'] for s in rows),page_hit=sum(s['page_hit'] for s in rows),page_rate=f'{sum(s["page_hit"] for s in rows)/len(rows):.3f}'))
    group_rows.append(dict(group='ALL',n=len(scored),work_hit=sum(s['work_hit'] for s in scored),page_hit=sum(s['page_hit'] for s in scored),page_rate=f'{sum(s["page_hit"] for s in scored)/len(scored):.3f}'))
    write_csv(out/'group_metrics.csv',group_rows)
    fallback=sum('本次未翻译' in r['raw_output'] for r in raw)
    deadline=[r['id'] for r in raw if '本次查询到了 60 秒上限' in r['raw_output']]
    if n<5:
        comp=load(out/'comparison.jsonl');assert [x['id'] for x in comp]==[x['id'] for x in scored]
        deltas=collections.Counter(x['0062_change'] for x in comp)
        prev=load(root/'rerun_0062/results.jsonl');assert [x['id'] for x in prev]==[x['id'] for x in scored]
        comparison=f'相对 0062：{dict(deltas)}；前轮到页 {sum(x["page_hit"] for x in prev)}/{len(prev)}。逐题见 comparison.jsonl。'
    else:
        write_jsonl(out/'comparison.jsonl',[dict(id=s['id'],group=s['group'],baseline='首次台式机题库，无前轮',work_hit=s['work_hit'],page_hit=s['page_hit'],same_work_pages=s['same_work_pages']) for s in scored])
        comparison='首次测试，无前轮逐题变化；逐题判定见 comparison.jsonl。'
    text=f'# 0069 round{n} 盲测\n\n题库 SHA-256 `{expected_hash[n]}`。冻结题正式调用各一次；按同作品、前五条、PDF 物理页 ±1 判定；没有改题或重跑。\n\n'
    text+='| 分组 | 题数 | 命中作品 | 命中作品且页 |\n|---|---:|---:|---:|\n'
    for r in group_rows:text+=f'| {r["group"]} | {r["n"]} | {r["work_hit"]} | {r["page_hit"]} |\n'
    text+=f'\n{comparison}\n\n自动翻译失败并回退中文原文：{fallback}/{len(raw)}；服务内部 60 秒截止（部分来源没完成）：{len(deadline)}，题号 {", ".join(deadline) or "无"}。成功退出码不等于所有索引路线都完成。原始逐题输出及片段均保存在本目录 results.jsonl，只供实验室内部核查，不向平台发题目或答案。\n'
    if n==5:
        hits=[s for s in scored if s['work_hit']]
        def flags(s):
            r=raw[next(i for i,x in enumerate(raw) if x['id']==s['id'])]
            target=[h for h in r['hits'][:5] if h['same_work']]
            return target
        path=sum(any('只在台式机能打开' in h['block'] and 'I:' in h['source_pdf'] for h in flags(s)) for s in hits)
        candidate=sum(any('题目候选' in h['heading'] for h in flags(s)) for s in hits)
        warning=sum(any('OCR 文本，引用前核原页' in h['block'] for h in flags(s)) for s in hits if s['group']=='ocr')
        oc=[s for s in hits if s['group']=='ocr']
        text+=f'\n同作品已召回的 {len(hits)} 题中，结果标“只在台式机能打开”且有 I:\\ 路径 {path}/{len(hits)}；带“题目候选”标题 {candidate}/{len(hits)}（标题非正式书目，不得计为正式题名）；OCR 同作品召回 {len(oc)} 题中带“引用前核原页”提示 {warning}/{len(oc)}。未召回时不能把前五条其他作品的来源/标题提示计为本题成功。\n'
        text+='\n本批 30/30 中文查询均提示翻译未完成而回退中文原文。Book 与 Literature 两组各 0/10 到页尤其受跨语检索失效混杂；保留正式一次跑分，不替换成翻译后成绩。R5-30 问句对椭圆孔方位/载荷限定不足，单列为未命中而不事后改题。OCR 五题原图由 Lead 在 `../ocr_visual_check_by_lead.md` 核验。\n'
    else:
        text+='\n此批部分题遭遇服务内部 60 秒限制，记录为当次服务可见的前五结果，不私下重试或挪出分母。\n'
    text+='\n结论：本次数字是按冻结题的一次现场结果；任何受翻译回退或内部截止混杂的组别不应用来断言索引本体质量。\n'
    write_md(out/'summary.md',text)
    print(n,group_rows,'fallback',fallback,'deadline',deadline)
