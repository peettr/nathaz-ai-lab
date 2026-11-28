from pathlib import Path
p=Path('/content/luw_city_ma010_1016/solver.log')
if p.exists():
 s=p.read_bytes()
 print('bytes',len(s))
 print(s[-2400:].decode(errors='replace'))
