from pathlib import Path
p=Path('/content/m5');p.mkdir(parents=True,exist_ok=True)
print(p.exists())
