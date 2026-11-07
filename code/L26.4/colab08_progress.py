from pathlib import Path
p=Path('/content/l264surface08');f=p/'resume_increment.jsonl'
print('resumed',len(f.read_text().splitlines()) if f.exists() else 0,'/ 40')
for x in list(p.rglob('*.part'))[:8]:print('partial',x.name,x.stat().st_size)
print('failure',(p/'run_resume.failed').exists())
