from pathlib import Path
import subprocess
for p in ['/content/luw_z0b.launch','/content/luw_z0b_FGz2/progress.log','/content/luw_z0b_FGz2/error.txt','/content/luw_z0b_FGz2/solver.exit','/content/luw_z0b_FGz6/progress.log','/content/luw_z0b_FGz6/error.txt']:
 x=Path(p);print(p,x.exists(),x.read_text()[-700:] if x.exists() else '')
print(subprocess.run(['pgrep','-af','remote_z0b.py'],capture_output=True,text=True).stdout)
