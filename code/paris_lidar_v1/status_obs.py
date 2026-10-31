import os,subprocess
from pathlib import Path
p=Path('/content/paris_a1');print('log', (p/'obs.log').read_text()[-3000:]);print('pidfiles', (p/'obs.pid').read_text());print('processes',subprocess.getoutput("ps -eo pid,etime,args | grep '[r]un_observations.py'"))
