from pathlib import Path
import subprocess
p=Path('/content/m5')
assert (p/'paris_gfs.exit').read_text().strip()=='0'
assert len(list((p/'paris_gfs').glob('*.csv')))==1104
assert len(list((p/'paris_obs').glob('palupd_*.csv')))==9
assert not (p/'paris_score.done').exists()
cmd='cd /content/m5; python3 -u m5_paris_score.py > paris_score.log 2>&1; rc=$?; printf "%s\\n" "$rc" > paris_score.exit; touch paris_score.done'
proc=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('PARIS_SCORE_PID',proc.pid)
