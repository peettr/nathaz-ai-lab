from pathlib import Path
import os,signal,re,time
r=Path('/content/luw-aij-caseA-turb-20261014');m=(r/'solver.metrics').read_text();pid=int(re.search(r'pid=(\d+)',m).group(1));print('stopping',pid,m,flush=True);os.kill(pid,signal.SIGTERM);time.sleep(2);print('exit',(r/'solver.exit').read_text() if (r/'solver.exit').exists() else 'pending',flush=True)
