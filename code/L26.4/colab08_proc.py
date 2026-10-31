from pathlib import Path
import subprocess
p=Path('/content/l264surface08')
print(subprocess.run(['ps','-eo','pid,stat,etime,args'],capture_output=True,text=True).stdout[-3500:])
for f in list(p.rglob('*.part'))[:12]:print('PART',f, f.stat().st_size)
print('STAGE', (p/'stage_resume.log').read_text()[-800:]);print('FAIL',(p/'run_resume.failed').exists())
