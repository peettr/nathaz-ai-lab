from pathlib import Path
import os,subprocess,time
r=Path('/content/luw-c38-cased-r8-20261115')
r.mkdir(exist_ok=False)
(r/'owner').write_text('R21.4 C38.2 Case D / researchos-uwind-luw\n')
(r/'deadline_epoch').write_text(str(float(os.environ['CASE_D_DEADLINE_EPOCH'])))
(r/'run.log').write_text('launcher '+time.strftime('%Y-%m-%d %H:%M:%S %z')+'\n')
f=(r/'wrapper.log').open('x')
p=subprocess.Popen(['python3','-u','/content/remote_caseD.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',p.pid, 'DEADLINE', (r/'deadline_epoch').read_text(),flush=True)
