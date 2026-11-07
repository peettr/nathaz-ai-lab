from pathlib import Path
import subprocess,sys,time
root=Path('/content/ace_formal')
(root/'stage.lock').open('x').write(str(time.time()))
log=(root/'stage.log').open('x')
runner='import subprocess,json,time,sys; t=time.monotonic(); r=subprocess.run([sys.executable,"/content/ace_formal/stage_inputs.py"],stdout=sys.stdout,stderr=subprocess.STDOUT); open("/content/ace_formal/stage.exit.json","x").write(json.dumps({"returncode":r.returncode,"wall_s":time.monotonic()-t})); sys.exit(r.returncode)'
p=subprocess.Popen([sys.executable,'-u','-c',runner],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'stage.pid').write_text(str(p.pid))
print('STAGING_STARTED',p.pid,flush=True)
