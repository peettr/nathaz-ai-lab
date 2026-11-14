from pathlib import Path
p=Path('/content/l2613v2_ground0.log');print(p.read_text()[-1000:] if p.exists() else 'NO LOG')
print('marker',Path('/content/l2613v2/stl_export_ground0.done').exists())
