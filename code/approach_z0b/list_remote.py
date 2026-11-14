from pathlib import Path
for p in Path('/content/luw_z0b_FGz2').glob('*.json'):print(p,p.stat().st_size)
for p in Path('/content/luw_z0b_FGz2').glob('*.csv'):print(p,p.stat().st_size)
