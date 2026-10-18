import subprocess,sys
from pathlib import Path
r=Path('/content/e_terrain_v2')
assert 'WN_V2_DONE 2068 0' in (r/'stage_b.log').read_text()
assert 'WN_V2_DONE 2131 0' in (r/'stage_test_b.log').read_text()
(r/'analysis_launch.lock').open('x').write('v2-revision')
log=(r/'analysis_v2.log').open('x');p=subprocess.Popen([sys.executable,str(r/'analyze_v2.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'analysis_v2.pid').write_text(str(p.pid));print('ANALYSIS_V2_LAUNCHED',p.pid,flush=True)
