import os,signal,subprocess
from pathlib import Path
R=Path('/content/luw_nan_stage4_retry3_1016')
print(subprocess.run(['ps','-eo','pid,ppid,args'],capture_output=True,text=True).stdout[-3500:])
# Kill only the solver under this exact isolated root, not other users' processes.
for p in Path('/proc').glob('[0-9]*'):
 try:
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='ignore')
  if str(R/'FluidX3D/bin/FluidX3D') in cmd and 'python' not in cmd:
   os.kill(int(p.name),signal.SIGTERM);print('TERM',p.name,cmd[:250])
 except (OSError,ValueError):pass
