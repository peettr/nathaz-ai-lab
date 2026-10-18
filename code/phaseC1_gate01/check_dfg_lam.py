from pathlib import Path
p=Path('/content/dfg_lam_progress.log')
print(p.read_text()[-1000:] if p.exists() else 'no progress')
for p in Path('/content').glob('lam_D*_full.csv'):print(p.name,p.stat().st_size)
