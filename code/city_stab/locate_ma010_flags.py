from pathlib import Path
r=Path('/content/luw_city_ma010_1016')
for p in r.rglob('*flags*'):
 print(str(p),p.stat().st_size)
