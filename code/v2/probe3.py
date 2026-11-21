from pathlib import Path
p=Path('/content/l2613v2_finish3.log');print(p.read_text()[-5000:] if p.exists() else 'NO LOG')
print((Path('/content/l2613v2/finish3.done')).exists())
