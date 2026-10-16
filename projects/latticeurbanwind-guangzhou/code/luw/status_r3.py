from pathlib import Path
r=Path('/content/luw-aij-r3');p=r/'solver.log'
print((r/'solver.exit').read_text() if (r/'solver.exit').exists() else (r/'solver.metrics').read_text() if (r/'solver.metrics').exists() else 'no marker')
if p.exists():
 text=p.read_text(errors='replace');print('LOG_FIRST\n',text[:10000]);print('LOG_LAST\n',text[-2000:])
