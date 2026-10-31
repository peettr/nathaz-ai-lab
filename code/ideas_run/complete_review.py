import csv, json, collections
from pathlib import Path

root=Path(__file__).parent
questions=[json.loads(x) for x in (root.parent/'questions_new20.jsonl').read_text().splitlines()]
logs=[json.loads(x) for x in (root/'query_log.jsonl').read_text().splitlines()]
rows=list(csv.DictReader((root/'top5_all_candidates.csv').open(newline='')))
lookup={(r['id'],r['mode']):r for r in logs}
assert len(questions)==20 and len(logs)==40 and len(rows)==200
assert len(lookup)==40 and all(r['exit_code']==0 for r in logs)
assert all(sum(x['id']==q['id'] and x['mode']==mode for x in rows)==5 for q in questions for mode in ('zh','en'))
assert all(x['thumb_cli_ok']=='True' and x['thumb_exists']=='True' for x in rows)
# The CLI's complete stdout, not reconstructed or abbreviated candidate text.
parts=['# 冻结题 0152：40 次原始 rc-kb figs 前五输出','',
       '每块为首次查询的原始 stdout（含图号、图注、题录、PDF 物理页）；未重查、未改写。来源：query_log.jsonl。','']
for q in questions:
    for mode in ('zh','en'):
        rec=lookup[(q['id'],mode)]
        parts+=['## '+q['id']+' '+('中文' if mode=='zh' else '英文'),'',
                '原问句：'+q['q' if mode=='zh' else 'q_en'],'',
                '```text',rec['stdout'].rstrip(),'```','']
(root/'results_top5.md').write_text('\n'.join(parts),encoding='utf-8')
byid=collections.defaultdict(list)
for r in rows: byid[r['fig_id']].append(r)
repeated={k:v for k,v in byid.items() if len(v)>1}
# A visual pass is a mandatory prerequisite; absence is scored as no *confirmed* hits,
# not as a claim that the candidate is actually irrelevant.
score=['# 冻结题 0152：严格确认命中计分（视觉复核未完成）','',
       '判据：前五中至少一图满足 hit 全部必要条件；图注、文献题目、缩略图三项均须核对。规格说明第 29 行禁止把缩略图交识图工具或其他模型。当前执行体不能用本机屏幕目视图像，所以“✗”只表示尚无可确认的命中，**不是已目视确认的不相关**。不得据此宣称工具失败或通过。所有 157 张不同缩略图已由 --thumb 取回且文件存在，但“已取图”不等于“已看图”。','',
       '| 题号 | 中文 | 中文理由 | 英文 | 英文理由 |','|---|---|---|---|---|']
for q in questions:
    req=q['hit'].replace('|','／').replace('\n',' ')
    reason='前五图注/题录已存；缩略图未获准交本模型目视，无法核定图面与裁切是否满足：'+req
    score.append(f"| {q['id']} | ✗（未确认） | {reason} | ✗（未确认） | {reason} |")
score+=['', '中文确认命中 0/20；英文确认命中 0/20。**这是证据不足的保守记法，不是完成视觉复判后的性能分数。**按事先双口径均 ≥14/20 的闸门，目前不能判“过”；也不能据此判“未过”。',
        '', '命中项已看缩略图：无（没有可证实命中项）。台式机不可达／--thumb 失败：0；200 个候选的 157 张不同缩略图已取回、均存在，但 200 个候选均未视觉核验。候选逐项的图号、图注、文献题目、页码、取图路径与视觉状态在 top5_all_candidates.csv。',
        '', '系统性观察（只依据文字结果，不把未看图片误作事实）：',
        f'- 前 200 个位置涉及 {len(byid)} 张不同图；{len(repeated)} 个图号跨题或中英文口径重复出现，重复占位数 {sum(len(v)-1 for v in repeated.values())}。去重后仍须逐题核看图。',
        '- 台式机来源部分题名为文件名式或截断文本，题录不足以独立判定主题；一些图注可对应题目的一半条件，但曲线坐标、面板与裁切完整性必须看图。',
        '- 不能判定某类题“全军覆没”：未完成视觉核验，按题材统计失败会制造伪结论。',
        '', '限制与后续：严格执行第 29 行时，只能由 Liang Hu 在本机逐项目视这批固定排名（不再重查），或者先由规则制定者明确批准一个不外送的视觉渠道。不能调用 vision_analyze 规避限制。',
        '']
(root/'SCORE.md').write_text('\n'.join(score),encoding='utf-8')
print(json.dumps({'blocks':len(logs),'candidate_rows':len(rows),'unique_thumbs':len(byid),'repeated_ids':len(repeated),'repeated_slots':sum(len(v)-1 for v in repeated.values()),'results_bytes':(root/'results_top5.md').stat().st_size,'score_bytes':(root/'SCORE.md').stat().st_size},ensure_ascii=False))
