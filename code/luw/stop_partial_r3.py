from pathlib import Path
import os,signal,time
r=Path('/content/luw-aij-r3');m=(r/'solver.metrics').read_text(); print('before stop',m)
pid=int(m.split('pid=')[1].split()[0]);os.kill(pid,signal.SIGTERM);time.sleep(2)
print('signal sent',pid,'exit marker',(r/'solver.exit').read_text() if (r/'solver.exit').exists() else 'pending')
