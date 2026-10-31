from pathlib import Path
p=Path('/content/l264surface07')
for name in ('resume.log','install_py310.log','pilot.log','resume.failed'):
 f=p/name
 print('\n'+name, 'MISSING' if not f.exists() else f'SIZE {f.stat().st_size}\nHEAD\n'+f.read_text(errors='replace')[:2500]+'\nTAIL\n'+f.read_text(errors='replace')[-700:])
for name in ('install_py310.done','pilot.json','budget_go','run.done'):
 f=p/name;print(name,'YES' if f.exists() else 'NO')
