import os, signal, subprocess
from pathlib import Path
p=Path('/content/m6')
assert (p/'train_gfs.exit').read_text().strip()=='0'
assert len(list((p/'train_gfs').glob('*.csv')))==376
assert (p/'m6_score.py').exists() and (p/'verify_section8_and_fit.py').exists()
# The temporary clarification-only heartbeat is no longer needed.
os.kill(172851, signal.SIGTERM)
command='cd /content/m6; python -u verify_section8_and_fit.py > section8_fit.log 2>&1; echo $? > section8_fit.exit; touch section8_fit.done'
a=subprocess.Popen(['bash','-lc',command],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('SECTION8_FIT_PID',a.pid)
