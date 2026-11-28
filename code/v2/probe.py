from pathlib import Path
p=Path('/content/l2613v2_finish.log');print(p.read_text()[-3000:] if p.exists() else 'NO LOG')
print(Path('/content/l2613v2/finish.done').exists())
