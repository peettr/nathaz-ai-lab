#!/usr/bin/env python3
"""Evaluate prewritten book questions and original Chinese set on extended PDF corpus."""
import csv,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import search as baseline
from bilingual import search as enhanced
R=Path('./22_Lab/06_Logs/fulltext_kb')
sets=[('books',R/'questions_books_supplement.jsonl'),('chinese_original',R/'questions.jsonl')]
rows=[]
for group,path in sets:
 qhash=hashlib.sha256(path.read_bytes()).hexdigest()
 for line in path.open():
  q=json.loads(line)
  for method,fn in [('bm25',baseline),('bilingual',enhanced)]:
   hits=fn(q['question'],5)
   row={'group':group,'question_id':q['id'],'question_sha256':qhash,'method':method,'answer_key':q['answer_key'],'answer_page':q['answer_page'],'page_hit5':int(any(x['key']==q['answer_key'] and abs(x['page']-q['answer_page'])<=1 for x in hits)),'document_hit5':int(any(x['key']==q['answer_key'] for x in hits)),'top5':json.dumps([{'key':x['key'],'page':x['page'],'title':x['title']} for x in hits],ensure_ascii=False)}
   rows.append(row)
   print(group,q['id'],method,row['page_hit5'],row['document_hit5'],flush=True)
tag=sys.argv[1] if len(sys.argv)>1 else 'v2'
with (R/f'retrieval_extended_rows_{tag}.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
with (R/f'retrieval_extended_metrics_{tag}.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['group','method','N','page_hits5','document_hits5','page_rate','document_rate']);w.writeheader()
 for group,_ in sets:
  for method in ('bm25','bilingual'):
   z=[x for x in rows if x['group']==group and x['method']==method];p=sum(x['page_hit5'] for x in z);d=sum(x['document_hit5'] for x in z)
   w.writerow({'group':group,'method':method,'N':len(z),'page_hits5':p,'document_hits5':d,'page_rate':p/len(z),'document_rate':d/len(z)})
