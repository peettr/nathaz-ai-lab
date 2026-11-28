import subprocess,sys
from pathlib import Path
r=Path('/content/e_terrain_v2');(r/'stage_launch.lock').open('x').write('v2-revision')
log=(r/'stage.log').open('x');p=subprocess.Popen([sys.executable,str(r/'stage_wn_v2.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'stage.pid').write_text(str(p.pid));print('STAGE_LAUNCHED',p.pid,flush=True)
