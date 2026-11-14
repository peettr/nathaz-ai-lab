from pathlib import Path
r=Path('/content/b2s_case')
for n in ['progress.log','error.txt','extract.log']:
 p=r/n
 if p.exists():print(n,p.read_text()[-1500:])
