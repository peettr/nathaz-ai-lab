from pathlib import Path
p=Path('/content/l264surface08')
for x in ['worker.log','stage.log','install.log','pilot.log','surface.log','run.failed','stage_increment.jsonl','stage.done','install_py310.done','equivalence.json','budget_go','run.done']:
 f=p/x
 print(x, 'MISSING' if not f.exists() else str(f.stat().st_size)+' bytes '+(f.read_text(errors='replace')[-1100:] if f.suffix in ('.log','.json','.jsonl') or x=='run.failed' else ''),flush=True)
