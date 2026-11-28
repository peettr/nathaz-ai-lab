from pathlib import Path
import subprocess
p=Path('/content/m6')
assert (p/'score_rebuilt.exit').read_text().strip()=='143'
assert not (p/'rebuild_core.launch').exists()
(p/'rebuild_core.launch').open('x').write('frozen core functions, no redundant secondary')
cmd='cd /content/m6; python -u m6_rebuild_core.py > rebuild_core.log 2>&1; echo $? > rebuild_core.exit; touch rebuild_core.done'
a=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('CORE_PID',a.pid)
