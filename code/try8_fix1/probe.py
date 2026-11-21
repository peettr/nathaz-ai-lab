from pathlib import Path
p=Path('/content/try8_fix1_controller.log')
print('LOG',p.read_text()[-7000:] if p.exists() else 'absent')
for f in ['/content/try8_fix1_done.marker','/content/try8_fix1_failed.marker','/content/try8_fix1_diag/build.log','/content/try8_fix1_diag/wall.log','/content/wall_gate0.csv','/content/wall_gate0_pulse.csv']:
 q=Path(f);print(f,q.exists(),q.stat().st_size if q.exists() else '',q.read_text()[-4000:] if q.exists() and q.suffix=='.log' else '')
