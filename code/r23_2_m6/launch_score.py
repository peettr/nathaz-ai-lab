from pathlib import Path
import hashlib, subprocess, os
p=Path('/content/m6')
assert (p/'test_gfs.exit').read_text().strip()=='0'
assert len(list((p/'test_gfs').glob('*.csv')))==368
assert hashlib.sha256((p/'m6_score.py').read_bytes()).hexdigest()=='11c7f845a502406d7232c67c2308fdca51d199d55d5d71c52f95448ce66ea39c'
assert hashlib.sha256((p/'config.json').read_bytes()).hexdigest()=='77491cc04c6a43fb0f5749298b3b17789ee73a7979c73a7f4b0e44f568835fc1'
assert (p/'models.json').exists()
with (p/'score.launch').open('x') as f: f.write('m6_score.py test\n')
command='cd /content/m6; python -u m6_score.py test > score.log 2>&1; echo $? > score.exit; touch score.done'
a=subprocess.Popen(['bash','-lc',command],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('SCORE_PID',a.pid)
