from pathlib import Path
p=Path('/content/full.log');print(p.read_text(errors='replace')[-4000:] if p.exists() else 'NO LOG')
r=Path('/content/luw_wp1_full');print('done', (r/'done.txt').read_text() if (r/'done.txt').exists() else 'pending')
