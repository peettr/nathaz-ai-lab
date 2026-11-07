from pathlib import Path
p=Path('/content/l26v2')
print('done', (p/'run.done').exists())
for name in ('answers_A.jsonl','answers_B.jsonl'):
 q=p/name;print(name,'lines',len(q.read_text().splitlines()) if q.exists() else 0)
q=p/'run.log';print('log tail:',q.read_text(errors='replace')[-4000:] if q.exists() else 'none')
