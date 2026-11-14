from pathlib import Path
p=Path('/content/a_original.log')
print('log',p.exists(),p.stat().st_size if p.exists() else 0,p.read_text()[-5000:] if p.exists() else '')
q=Path('/content/a_original.exit')
print('exit',q.read_text() if q.exists() else None)
print('rows',Path('/content/a_original_rows.csv').exists())
