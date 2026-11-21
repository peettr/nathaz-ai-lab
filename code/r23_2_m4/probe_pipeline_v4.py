from pathlib import Path
import subprocess
r=Path('/content/m4')
p=r/'pipeline_v4.log'
print('LOG',p.exists(),p.read_text()[-2500:] if p.exists() else '')
print('DONE',(r/'pipeline_v4.done').exists(),'EXIT',(r/'pipeline_v4.exit').read_text() if (r/'pipeline_v4.exit').exists() else None)
print('PROC',subprocess.run(['pgrep','-af','run_all_v4.sh'],capture_output=True,text=True).stdout)
print('CHECKPOINTS',[(x.name,x.stat().st_size) for x in r.glob('checkpoint_*.tgz')])
