from pathlib import Path
p=next(Path('/content').glob('luw_iso_*_1015'),None)
print('ROOT',p)
if p:
 for n in ['progress.log','error.txt','build.log','solver.log','all.done']:
  f=p/n
  print(n, f.exists(), f.read_text()[-1300:] if f.exists() else '')
