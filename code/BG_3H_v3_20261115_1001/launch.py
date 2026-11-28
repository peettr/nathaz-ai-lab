from pathlib import Path
import os,subprocess,time
r=Path('/content/luw-c38-bg3h-v3-20261115_1001')
r.mkdir(exist_ok=False)
(r/'owner').write_text('R21.4 C38.2 BG_3H / researchos-uwind-luw\n')
(r/'deadline_epoch').write_text(str(float(os.environ['BG_DEADLINE_EPOCH'])))
(r/'run.log').write_text('launcher '+time.strftime('%Y-%m-%d %H:%M:%S %z')+'\n')
f=(r/'wrapper.log').open('x')
p=subprocess.Popen(['python3','-u','/content/remote_BG.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',p.pid, 'DEADLINE', (r/'deadline_epoch').read_text(),flush=True)
