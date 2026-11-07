from pathlib import Path
import subprocess
for name in ('a_stage_v2.log','a_stage_v2.exit','a_stage_v2.done','a_inputs_v2/manifest.json'):
 p=Path('/content')/name; print(name,p.exists(),p.stat().st_size if p.exists() else '',p.read_text()[-2500:] if p.exists() and p.suffix in ('.log','.exit') else '')
print(subprocess.run(['ps','-eo','pid,etime,args'],capture_output=True,text=True).stdout[-3000:])
