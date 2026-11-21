from pathlib import Path
for tag in ('E1G0A35','E1G0A70'):
 r=Path('/content/luw_keep2_'+tag)
 print(tag, (r/'solver.exit').read_text(), (r/'all.done').exists())
 for p in sorted((r/'case/RESULTS').rglob('*')):
  if p.is_file() and (p.suffix in ('.csv','.json') or p.name.endswith('avg.vtk')):
   print(p, p.stat().st_size)
 print('EXTRACT',[(p.name,p.stat().st_size) for p in r.glob('*.json')])
