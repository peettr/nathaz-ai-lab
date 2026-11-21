from pathlib import Path
p=Path('/content/l264surface07')
for name in ('second_resume.log','pilot02.log','pilot02.json','second_resume.failed','surface.log'):
 f=p/name
 print(name,'MISSING' if not f.exists() else f'SIZE {f.stat().st_size} HEAD {f.read_text(errors="replace")[:1600]} TAIL {f.read_text(errors="replace")[-500:]}')
