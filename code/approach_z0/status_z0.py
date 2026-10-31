from pathlib import Path
import subprocess
for p in ['/content/luw_z0.launch','/content/luw_z0_FG0z/progress.log','/content/luw_z0_FG0z/error.txt','/content/luw_z0_FG0z/solver.exit','/content/luw_z0_FG0zA70/progress.log']:
 x=Path(p);print(p, x.exists(),x.read_text()[-1300:] if x.exists() else '')
print(subprocess.run(['pgrep','-af','remote_z0.py'],capture_output=True,text=True).stdout)
