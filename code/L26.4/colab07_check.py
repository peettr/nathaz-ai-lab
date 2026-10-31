from pathlib import Path
p=Path('/content/l264surface07')
for name in ('worker.log','stage.log','install.log','pilot.log','surface.log','run.failed'):
 f=p/name
 print(name,'MISSING' if not f.exists() else f'SIZE {f.stat().st_size} TAIL\n'+f.read_text(errors='replace')[-2200:])
for name in ('stage_increment.jsonl','stage.done','install.done','pilot.json','budget_go','run.done'):
 f=p/name
 print(name, f.stat().st_size if f.exists() else 'MISSING')
