from pathlib import Path
p=Path('/content/e_terrain/full/forecast_parts')
for f in p.glob('ERROR_*'):
 print(f.name, f.read_text()[-1200:])
