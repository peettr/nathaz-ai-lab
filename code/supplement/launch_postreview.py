from pathlib import Path
import subprocess,json
p=Path('/content/m6')
assert (p/'rebuild_core.exit').read_text().strip()=='0'
assert json.loads((p/'rebuild_core/parity.json').read_text())['passed']
assert not (p/'postreview.launch').exists()
(p/'postreview.launch').open('x').write('post-freeze after core parity')
cmd='cd /content/m6; python -u m6_postreview.py > postreview.log 2>&1; echo $? > postreview.exit; touch postreview.done'
a=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('POST_PID',a.pid)
