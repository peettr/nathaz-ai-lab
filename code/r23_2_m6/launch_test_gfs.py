import hashlib, subprocess
from pathlib import Path
p=Path('/content/m6')
assert (p/'section8_fit.exit').read_text().strip()=='0'
assert (p/'models.json').exists() and not (p/'test_gfs.done').exists()
assert hashlib.sha256((p/'m6_score.py').read_bytes()).hexdigest()=='11c7f845a502406d7232c67c2308fdca51d199d55d5d71c52f95448ce66ea39c'
assert hashlib.sha256((p/'config.json').read_bytes()).hexdigest()=='77491cc04c6a43fb0f5749298b3b17789ee73a7979c73a7f4b0e44f568835fc1'
command='cd /content/m6; python -u m6_extract.py test > test_gfs.log 2>&1; echo $? > test_gfs.exit; touch test_gfs.done'
a=subprocess.Popen(['bash','-lc',command],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('TEST_GFS_PID',a.pid)
