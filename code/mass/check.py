from pathlib import Path
for n in ['D_v2','M1','M2']:
 p=Path('/content/mass_'+n)
 if p.exists():
  print(n,'done',(p/'done').exists(),'progress',((p/'progress.log').read_text()[-1000:] if (p/'progress.log').exists() else '?'))
  q=p/'stage/case/RESULTS/mass_extrema.csv'
  if q.exists():
   with q.open() as f:
    import collections
    tail=collections.deque(f,maxlen=2)
   print('tail',list(tail))
