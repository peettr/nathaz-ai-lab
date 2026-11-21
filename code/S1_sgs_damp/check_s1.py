from pathlib import Path
r=Path('/content/s1_case')
for name in ('progress.log','error.txt','solver.exit','all.done','build.log'):
 p=r/name
 print(name,p.exists(),p.read_text()[-1000:] if p.exists() else '')
print('driver',Path('/content/s1_driver.log').read_text()[-1000:])
