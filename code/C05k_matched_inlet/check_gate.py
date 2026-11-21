from pathlib import Path
r=Path('/content/c05k_gate_01')
print('exists',r.exists(),'done',(r/'all.done').exists())
for n in ('progress.log','error.txt','build.log','solver.log','gate_profiles.json'):
 p=r/n
 print(n,p.stat().st_size if p.exists() else 'missing')
 if p.exists() and n in ('progress.log','error.txt','build.log','solver.log'):
  print(p.read_text(errors='replace')[-1200:])
