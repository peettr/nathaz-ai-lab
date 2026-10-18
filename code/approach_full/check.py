from pathlib import Path
for p in sorted(Path('/content').glob('luw_full_*')):
 print(p.name, 'progress=',(p/'progress.log').read_text()[-600:] if (p/'progress.log').exists() else 'none','launch=',Path('/content/'+p.name.replace('luw_full_','')+'.launch').read_text()[-600:] if Path('/content/'+p.name.replace('luw_full_','')+'.launch').exists() else 'none',flush=True)
