from pathlib import Path
import subprocess,time,os
r=Path('/content/r216_caseA_0b');r.mkdir(exist_ok=True)
(r/'EXPERIMENT_CARD.md').write_bytes(Path('/content/EXPERIMENT_CARD.md').read_bytes())
(r/'owner').write_text('R21.6-0b researchos-uwind-luw')
Path('/content/r216_session_start').write_text(str(time.time()))
assert not (r/'launch.lock').exists();(r/'launch.lock').touch(exist_ok=False)
f=(r/'launcher.log').open('w')
p=subprocess.Popen(['python3','-u','/content/run_remote.py'],cwd=r,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('SESSION_START',Path('/content/r216_session_start').read_text(),'LAUNCHED_PID',p.pid,flush=True)
