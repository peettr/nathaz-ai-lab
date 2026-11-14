from pathlib import Path
import subprocess,sys,os,json,time
root=Path('/content/ace_formal/reference');root.mkdir(exist_ok=True)
if (root/'batch.lock').exists() or (root/'batch.exit.json').exists():raise RuntimeError('Refuse duplicate reference process')
(root/'batch.lock').open('x').write(str(time.time()))
log=(root/'batch.log').open('x')
runner='import subprocess,json,time,sys; t=time.monotonic(); r=subprocess.run([sys.executable,"/content/ace_formal/extract_reference.py"],stdout=sys.stdout,stderr=subprocess.STDOUT,env={**__import__("os").environ,"FIRST_SEASON":"1980","LAST_SEASON":"2021"}); open("/content/ace_formal/reference/batch.exit.json","x").write(json.dumps({"returncode":r.returncode,"wall_s":time.monotonic()-t})); sys.exit(r.returncode)'
p=subprocess.Popen([sys.executable,'-u','-c',runner],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'batch.pid').write_text(str(p.pid))
print('REF_STARTED',p.pid,flush=True)
