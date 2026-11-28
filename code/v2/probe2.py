from pathlib import Path
p=Path('/content/l2613v2_finish2.log');print(p.read_text()[-5000:] if p.exists() else 'NO LOG')
print((Path('/content/l2613v2/finish2.done')).exists())
