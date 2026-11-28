from pathlib import Path
r=Path('/content/luw_city_ma010_v2_1016')
for p in (r/'case/RESULTS').glob('*'):
 print(p.name,p.stat().st_size)
