import json, pathlib, collections
root=pathlib.Path(__file__).resolve().parent
rows=[json.loads(s) for s in (root/'adjudicated_strict_mapped.jsonl').read_text().splitlines()]
assert len(rows)==len({x['id'] for x in rows})==30
assert sum(x['work_hit'] for x in rows)==21 and sum(x['page_hit'] for x in rows)==16
assert collections.Counter(x['page_change'] for x in rows)=={'不变':19,'变好':8,'变差':3}
report=root.parent.parent/'acceptance_0069_20261016.md'
assert '0151 第三轮复测' not in report.read_text(), 'section exists: no overwrite'
parts=['\n## 0151 第三轮复测（10-18 08:42 EDT）\n',
'冻结 R5 `questions_blind.jsonl` SHA-256 `8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07`，30 题未改；每题单独调用 `rc-kb pages -n 5`，外层单题 90 s、终端超时 ≥150 s。30/30 返回成功、0 外层超时；本轮累计查询用时 776.72 s。只读索引。原始响应 `blind_round5/results_0151/results.jsonl`，逐题裁决 `adjudicated_strict_mapped.jsonl`，配对表 `comparison_strict_mapped.jsonl`；这些含私有题库信息，不交平台。\n',
'严格前五判据：目标 DSK 哈希前缀或题库冻结路径命中同作品，PDF 物理页 ±1 到页；若展示的另一副本有明确「同页文字」的目标 DSK 映射页码，用目标副本的页码裁决，不能把另一版本的主副本页码套用。题名相似、摘录相似不扩张命中。相对 `results_rerun/summary_strict.md` 的作品 15/30、到页 11/30，本轮作品 21/30、到页 16/30。分组：Book 7/10 作品、5/10 到页（旧 5/10、4/10）；Literature 7/10、6/10（旧 4/10、4/10）；中文 4/5、3/5（旧 2/5、1/5）；OCR 3/5、2/5（旧 4/5、2/5）。到页逐题 8 变好、3 变差、19 不变；作品逐题 10 变好、4 变差、16 不变。全轮翻译成功 30/30、「未翻译」0、内部 60 秒上限提示 0、明确台式机来源没跑完提示 0。\n',
'逐题配对（作品/到页用 ✓、×；到页变化以旧版到页为基准）：\n',
'| ID | 组 | 原作品/页 | 0151 作品/页 | 页变化 |\n|---|---|---|---|---|\n']
for x in rows:
 mark=lambda b:'✓' if b else '×'
 parts.append(f"| {x['id']} | {x['group']} | {mark(x['old_work_hit'])}/{mark(x['old_page_hit'])} | {mark(x['work_hit'])}/{mark(x['page_hit'])} | {x['page_change']} |\n")
parts.extend(['\n变差线索（均无内部 60 秒上限、无台式机来源未跑完提示，且 rc-kb 正常退出；只说明排名构成变化，不归因为单一代码改动）：\n',
'- R5-01：旧轮目标 DSK 在第 4 位、目标物理页 56；本轮前五无目标作品，前列改由非目标论文/其他资料占据。\n',
'- R5-08：旧轮目标 DSK 在第 4 位、目标物理页 175；本轮前五虽有其他概率/模拟著作，但无目标 DSK 或冻结路径。\n',
'- R5-29：旧轮目标 DSK 在第 5 位、目标物理页 159；本轮前五出现另一部地震工程著作和相关文献，目标 DSK 未进入前五。\n',
'副本页码核验：21 道命中正确作品的题中，R5-03 展示目标副本物理页 80，冻结目标为 50（错；主副本页 250 更不能套用）；R5-05 展示目标副本 26 对冻结 26（对）；R5-26 的同一作品第 1 位给目标副本 198（冻结 196，超出 ±1），第 2 位给目标副本 196（对，故该题计到页）。其余 18 道正确作品题未见需要对目标副本另换算的明确映射页码；直接原件/同路径裁决。不凭展示页码单独验证原 PDF 的正文真实性，此处核对的是冻结真值与返回映射的一致性。\n',
'题名/路径展示：正确作品题 21/21 给出“只在台式机能打开”的路径，18/21 至少一条正确作品候选仍标「题目候选」，0/21 出现所检十六进制乱码题名；其余 3/21 未标候选，但未据此认定书目已独立核实。仍有文件名式候选（例如会议编号或文件夹名），故“未乱码”不等于题名可靠。\n',
'裁决注意：最早的 `results_0151/adjudicated_strict.jsonl` 是未将目标副本的显式同页映射用于到页判定的初始审计稿，R5-26 被低估；它原样保留，不用于本节。最终以 `adjudicated_strict_mapped.jsonl` 为准。可报告“总到页未退步”，但已有三题逐题变差，若删除旧索引备份的条件是“复测不退步”且包含逐题口径，这个闸门未通过；题目与答案、片段均不向平台交付。\n'])
with report.open('a') as f:f.write(''.join(parts))
print('appended',report,'rows',len(rows),'chars',len(''.join(parts)))
