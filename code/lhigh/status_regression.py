from pathlib import Path
p=Path('/content/lhigh_regression/progress.log')
print(p.read_text()[-1500:] if p.exists() else 'not yet')
