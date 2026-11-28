from pathlib import Path
p=Path('/content/l264a100/texas');f=p/'pilot03.log';print('PILOT_TAIL',f.read_text(errors='replace')[-3500:] if f.exists() else 'missing',flush=True)
q=p/'predictions/texas_texas_surface_01.npz';print('PILOT_RESULT',q.exists(),q.stat().st_size if q.exists() else 0,flush=True)
print('STAGING',Path('/content/l264a100/fast_data/fast.log').read_text()[-500:],flush=True)
