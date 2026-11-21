from pathlib import Path
r=Path('/content/luw_crop_v2_C1widev2')
for name in ('progress.log','error.txt','solver.exit','build.log'):
 p=r/name
 print(name, p.read_text()[-1800:] if p.exists() else 'missing')
for name in ('native_flags_z0_90.bin','extrema.csv','city_stability.csv'):
 p=r/'case/RESULTS'/name
 print(name,p.stat().st_size if p.exists() else 'missing')
