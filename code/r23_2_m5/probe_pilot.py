from pathlib import Path
import subprocess
r=Path('/content/m5')
for x in ('pilot.log','pilot.exit','pilot.done','progress.jsonl','errors.jsonl'):
 p=r/x;print(x,p.exists(),p.stat().st_size if p.exists() else '',p.read_text()[-1200:] if p.exists() and p.stat().st_size<100000 else '')
print(subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout[-1500:])
