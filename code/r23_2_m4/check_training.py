from pathlib import Path
p=Path('/content/m4/train.log')
print(p.read_text()[-3000:] if p.exists() else 'no log')
print('done',Path('/content/m4/train.done').exists())
