from pathlib import Path
p=Path('/content/l264surface08')
for name in ['stage_resume.log','worker_resume.log','run_resume.failed','stage.done','install.log','pilot.log','equivalence.json','surface.log','run.done']:
 f=p/name
 print(name, f.read_text(errors='replace')[-1400:] if f.exists() else 'missing',flush=True)
