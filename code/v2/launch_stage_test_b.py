import subprocess,sys
from pathlib import Path
r=Path('/content/e_terrain_v2');assert 'FORECAST_DONE' in (r/'forecast_v2.log').read_text()
(r/'stage_test_b_launch.lock').open('x').write('v2-revision')
log=(r/'stage_test_b.log').open('x');p=subprocess.Popen([sys.executable,str(r/'stage_test_v2b.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'stage_test_b.pid').write_text(str(p.pid));print('STAGE_TEST_B_LAUNCHED',p.pid,flush=True)
