from pathlib import Path
r=Path('/content/luw_c3_linear_1016')
for p in [r/'progress.log',r/'error.txt',Path('/content/bisect_driver.log')]:
 if p.exists():print(p.name,p.read_text(errors='replace')[-4000:])
for p in sorted(r.glob('B*/build.log')):
 print(p.parent.name,'build',p.read_text(errors='replace')[-400:])
for p in sorted(r.glob('B*/solver.log')):
 print(p.parent.name,'solver',p.read_text(errors='replace')[-800:])
for p in sorted(r.glob('L*/solver.log')):
 print(p.parent.name,'solver',p.read_text(errors='replace')[-800:])
print('done', (r/'all.done').exists())
