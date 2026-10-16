from pathlib import Path
import subprocess,os,time
r=Path('/content/luw-aij'); repo=r/'repo'; cmd=['uv','pip','install','--python',str(repo/'.venv/bin/python'),'-r',str(repo/'installer/requirements.txt')]
f=(r/'install_uv.log').open('w'); start=time.time(); p=subprocess.Popen(cmd,cwd=repo,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(r/'install_uv.pid').write_text(str(p.pid)); (r/'install_uv.start').write_text(str(start));print('pid',p.pid,'cmd',cmd)
