from pathlib import Path
p=Path('/content/m5')
for n in ['sectors.csv','m5_paris_score.py','paris_score.done','paris_gfs','paris_obs']:
 q=p/n
 print(n,q.exists(),len(list(q.glob('*.csv'))) if q.is_dir() else (q.stat().st_size if q.exists() else -1))
