import subprocess,sys
from pathlib import Path
r=Path('/content/e_terrain_v2');(r/'stage_b_launch.lock').open('x').write('v2-revision')
log=(r/'stage_b.log').open('x');p=subprocess.Popen([sys.executable,str(r/'stage_wn_v2b.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'stage_b.pid').write_text(str(p.pid));print('STAGE_B_LAUNCHED',p.pid,flush=True)
