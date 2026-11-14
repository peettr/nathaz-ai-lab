from pathlib import Path
r=Path('/content/b2u_case')
for name in ['progress.log','error.txt','build.log','short_solver.log','case_solver.log','all.done']:
 p=r/name
 print(name,p.exists(),p.stat().st_size if p.exists() else '',p.read_text()[-1200:] if p.exists() and name not in ['case_solver.log','build.log'] else '')
