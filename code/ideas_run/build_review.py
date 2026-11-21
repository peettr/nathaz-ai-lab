import pathlib, re, json, csv, collections
R=pathlib.Path(__file__).parent
qs={x['id']:x for x in map(json.loads,(R.parent/'questions_set2.jsonl').read_text().splitlines())}
jud=json.loads((R/'judgments.json').read_text())
blocks=[]; queue=[]; grades=collections.Counter(); per=collections.Counter()
rawdoc=['# 第二套冻结题：rc-kb figs 原始前五输出','', '输入 SHA256: 094a8db049c1bc24b8af5132019f20a73ae3a300c14911804a6c5a0040a648c9。每口径只查询一次；以下不修整服务返回的正文。','']
textdoc=['# 第二套题文字分档（未看缩略图）','', 'A=图注/题录可确认全部必要文字条件；B=主题吻合但必要条件尚须图面或来源确认；C=主题不符或至少一项明确不满足。A/B仍非最终图像命中。','']
for id,q in qs.items():
 for lg,key in [('zh','q'),('en','q_en')]:
  block=f'{id}_{lg}'; s=(R/'raw'/f'{block}.txt').read_text()
  assert s.startswith('EXIT_CODE=0\nQUERY='+q[key]+'\n')
  body=s.split('\n',2)[2].split('\nSTDERR:\n')[0].strip()
  rawdoc += [f'## {block}',f'问句：{q[key]}','```text',body,'```','']
  chunks=re.split(r'(?m)^\d+\. ',body)[1:]
  assert len(chunks)==5,(block,len(chunks))
  ab=jud[block]; seen=set(); textdoc += [f'## {block}',f'命中判据：{q["hit"]}','']
  for rank,chunk in enumerate(chunks,1):
   m=re.search(r'图号 ([a-f0-9]{24})',chunk); assert m,(block,rank)
   fig=m.group(1); lines=chunk.strip().splitlines(); caption=lines[0].strip(); citation=next((x.strip() for x in lines if '出处：' in x),'')
   grade=next((g for g,rr in ab.items() if str(rank) in rr),'C'); assert grade in 'ABC'
   if grade!='C':
    reason=ab[grade][str(rank)]; seen.add((grade,str(rank)))
    queue.append([block,rank,fig,grade,reason,''])
   else: reason='图注/题录仅涉及「'+caption[:85].replace('|','／')+'」，未同时指向本题全部必要主题或明确落在排除项；不纳入看图队列。'
   grades[grade]+=1
   if grade=='A': per[lg]+=1
   textdoc += [f'{rank}. {grade} · {fig} · {caption}',f'   {citation}',f'   理由：{reason}']
  assert seen=={(g,k) for g,rr in ab.items() for k in rr},(block,seen,ab)
  textdoc += ['', 'A/B：'+ ('；'.join(f'{g} '+','.join(chunks[int(k)-1].split('图号 ')[1][:24] for k in rr) for g,rr in ab.items() if rr) or '无'), '']
(R/'results_top5.md').write_text('\n'.join(rawdoc))
textdoc[1:1]=[f'逐候选总计 A {grades["A"]}、B {grades["B"]}、C {grades["C"]}；仅有 A 的块：中文 {per["zh"]}/20，英文 {per["en"]}/20。','']
(R/'TEXT_SCORE.md').write_text('\n'.join(textdoc))
with (R/'VISUAL_QUEUE.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['block','rank','fig_id','档位','待看图确认的条件','缩略图本机路径']);w.writerows(queue)
print('blocks',len(qs)*2,'grades',dict(grades),'queue',len(queue),'unique',len({x[2] for x in queue}))
