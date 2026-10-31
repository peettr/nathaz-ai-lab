from pathlib import Path
p=Path('/content')
for t in ('main','hours6','hours18','weight01','weight1','bdeck'):
 b=p/f'a_v3_r2_{t}'
 print(t,'exit',b.with_suffix('.exit').read_text().strip() if b.with_suffix('.exit').exists() else 'running','bytes',b.with_suffix('.csv').stat().st_size if b.with_suffix('.csv').exists() else 0)
print('done',(p/'a_v3_r2.done').exists())
