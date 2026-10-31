from pathlib import Path
r=Path('/content/luw_E1_split_1017')
for f in ('progress.log','solver.exit','error.txt'):
 p=r/f
 print(f, p.read_text()[-1800:] if p.exists() else 'missing')
print('driver',Path('/content/E1_driver.log').read_text()[-1000:])
