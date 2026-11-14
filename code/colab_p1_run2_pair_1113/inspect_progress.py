from pathlib import Path
for d in sorted(Path('/content/a170_2/runs').glob('run_P1_power_s*_G1')):
 print('RUN',d)
 for p in d.glob('*.out'):
  print(p.name,p.stat().st_size)
 for p in d.glob('*.log'):
  print(p.name,p.stat().st_size,p.read_text()[-300:])
