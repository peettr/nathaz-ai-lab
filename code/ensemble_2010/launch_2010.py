from pathlib import Path
import subprocess,sys,time,os
month=int(os.environ['MONTH']);assert 2<=month<=10
root=Path('/content/ace_formal/members');root.mkdir(exist_ok=True)
label=f'm{month:02d}'
if (root/label).exists() or (root/f'{label}.lock').exists():raise RuntimeError('Refuse duplicate '+label)
(root/f'{label}.lock').open('x').write(str(time.time()))
log=(root/f'{label}.launcher.log').open('x')
p=subprocess.Popen([sys.executable,'-u','/content/ace_formal/run_member_2010.py',str(month)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/f'{label}.pid').open('x').write(str(p.pid))
print('MEMBER_STARTED',label,p.pid,flush=True)
