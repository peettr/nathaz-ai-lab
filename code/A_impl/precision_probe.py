from pathlib import Path
p=Path('/content/precision.log')
print(p.read_text(errors='replace')[-6000:] if p.exists() else 'NO LOG')
