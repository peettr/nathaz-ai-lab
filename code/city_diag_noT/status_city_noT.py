from pathlib import Path
r=Path('/content/luw_city_diag_not_1016')
for name in ['progress.log','error.txt','build.log','G0/latest.json','G1/latest.json','G2/latest.json']:
 p=r/name
 print(name, p.read_text(errors='replace')[-1300:] if p.exists() else 'absent')
print('done', (r/'all.done').exists())
