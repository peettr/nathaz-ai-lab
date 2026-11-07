import subprocess,os
from pathlib import Path
p=Path('/content/paris_a1');p.mkdir(exist_ok=True)
(p/'.colab_owner').write_text('A1 Paris lidar researchos-lab-ideas 10-14 18:35 EDT\n')
with (p/'obs.log').open('a') as log:
 q=subprocess.Popen(['python','-u','/content/run_observations.py'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(p/'obs.pid').write_text(str(q.pid));print('OBS_PID',q.pid,flush=True)
