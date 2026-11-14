from pathlib import Path
import subprocess,hashlib
p=Path('/content/m6')
assert (p/'rebuild_gfs_fix.exit').read_text().strip()=='0'
assert len(list((p/'test_gfs').glob('*.csv')))==368
assert not (p/'score_rebuilt.launch').exists()
assert hashlib.sha256((p/'m6_score.py').read_bytes()).hexdigest()=='11c7f845a502406d7232c67c2308fdca51d199d55d5d71c52f95448ce66ea39c'
assert (p/'frozen_main.csv').exists()
assert not (p/'output_final/main.csv').exists()
(p/'score_rebuilt.launch').open('x').write('frozen scorer, comparison first')
cmd='cd /content/m6; python -u m6_score.py test > score_rebuilt.log 2>&1; echo $? > score_rebuilt.exit; touch score_rebuilt.done'
a=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('SCORE_PID',a.pid)
