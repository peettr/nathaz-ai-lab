from pathlib import Path
r=Path('/content/luw_wp1_full')
for p in [r/'none/solver.log',r/'none/FluidX3D/bin/kernel.log']:
 print(p,p.stat().st_size if p.exists() else None,p.read_text(errors='replace')[-1800:] if p.exists() else '')
