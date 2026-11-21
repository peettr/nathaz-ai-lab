import subprocess,time,os
from pathlib import Path
p=Path('/content/cache_run');p.mkdir(exist_ok=True)
cmd='apt-get update -qq && apt-get install -y -qq aria2 ninja-build cmake && python3 -m pip install -q cmake ninja psutil requests urllib3 && git clone -q https://github.com/Niko1221/Strata.git /content/Strata && git -C /content/Strata checkout -q v0.1.45'
log=open(p/'bootstrap.log','w',buffering=1)
with open(p/'bootstrap.exit','w') as f:f.write('running')
with open('/dev/null') as devnull:
 proc=subprocess.Popen(['bash','-lc',cmd],stdout=log,stderr=subprocess.STDOUT,stdin=devnull,start_new_session=True)
(p/'bootstrap.pid').write_text(str(proc.pid))
print('BOOTSTRAP_PID',proc.pid,flush=True)
