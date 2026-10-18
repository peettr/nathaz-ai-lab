from pathlib import Path
r=Path('/content/luw-aij')
print('done',(r/'avg.exit').read_text() if (r/'avg.exit').exists() else 'running')
p=r/'avg.log'; s=p.read_text(errors='replace') if p.exists() else ''
print('bytes',len(s),'tail',s[-2400:].replace('\r','\n')[-2400:])
print('vtk',[(q.name,round(q.stat().st_size/1e6)) for q in (r/'case_avg/RESULTS/vtk').glob('*')] if (r/'case_avg/RESULTS/vtk').exists() else 'none')
