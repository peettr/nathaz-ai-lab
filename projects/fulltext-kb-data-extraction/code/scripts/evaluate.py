#!/usr/bin/env python3
import csv,json,re,subprocess,sys,time,hashlib,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import search
R=Path('./22_Lab/06_Logs/fulltext_kb')
LANG=sys.argv[1] if len(sys.argv)>1 else 'zh'
TAG=sys.argv[2] if len(sys.argv)>2 else LANG
Q=R/('questions_en.jsonl' if LANG=='en' else 'questions.jsonl');qs=[json.loads(s) for s in Q.open()]
assert len(qs)>=30 and sum(x['card'] for x in qs)>=10 and sum(not x['card'] for x in qs)>=10
CTX='[已隐去]'
rows=[]
for j,q in enumerate(qs,1):
 out=subprocess.run(['rc-kb','--ctx',CTX,'search',q['question'],'-n','5'],capture_output=True,text=True,timeout=35).stdout
 blocks=re.split(r'(?m)^\d+\. ',out)[1:]
 kb=[]
 for block in blocks:
  m=re.search(r'\b[A-Z0-9]{8}\b',block)
  kb.append({'key':m.group() if m else None,'raw':block[:600]})
 bm=search(q['question'],5)
 def met(a):return int(any(x.get('key')==q['answer_key'] and abs(x.get('page',-100)-q['answer_page'])<=1 for x in a)),int(any(x.get('key')==q['answer_key'] for x in a))
 bpage,bpaper=met(bm);_,kpaper=met(kb)
 rows.append(dict(id=q['id'],topic=q['topic'],card=q['card'],key=q['answer_key'],page=q['answer_page'],bm25_page5=bpage,bm25_paper5=bpaper,rc_kb_paper5=kpaper,rc_kb_page5='不可判（搜索结果无可靠物理页）',bm25_top5=[{'key':x['key'],'page':x['page'],'title':x['title'],'score':x['rank']} for x in bm],rc_kb_top5=kb))
 if j%10==0:print('scored',j,flush=True)
with (R/f'retrieval_results_{TAG}.jsonl').open('x') as f:
 for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
with (R/f'retrieval_metrics_{TAG}.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['system','N','page_hits5','page_rate','paper_hits5','paper_rate','question_sha256']);w.writeheader()
 for method in ['bm25','rc_kb']:
  ph=sum(x[method+'_page5']==1 for x in rows);kh=sum(x[method+'_paper5']==1 for x in rows)
  w.writerow(dict(system=method,N=len(rows),page_hits5=ph,page_rate=f'{ph/len(rows):.3f}' if method=='bm25' else 'NA',paper_hits5=kh,paper_rate=f'{kh/len(rows):.3f}',question_sha256=hashlib.sha256(Q.read_bytes()).hexdigest()))
print('metrics',[(m,sum(x[m+'_paper5']==1 for x in rows)) for m in ('bm25','rc_kb')])
