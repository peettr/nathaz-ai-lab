"""One-shot VM1 launcher: verify frozen inputs before detached install/inference."""
import datetime as dt
import hashlib
import os
import pathlib
import subprocess
import sys

EXPECTED = {
    '/content/events_r4.csv': '8a01f4e2b910df3dc05a67eef35fa054c3b2110595bf1e71f758b9e2190e90e7',
    '/content/controls_r4.csv': 'e4eee460a2e3e6e055dbc27e5eb5eba774bd3bcafce4b0c69a015b9c34674bd1',
    '/content/r4_worker_v2.py': '74babd0b95df54916e886258c5708969951331ce7def56201670b34669340f1a',
    '/content/r4_score_v4.py': '5f479e4dc509cd61b1964c4f195b1bf7c01bc5a2bd62d0a88f47b8b4205ba382',
}
root = pathlib.Path('/content/r4_s2')
root.mkdir(exist_ok=True)
for name, digest in EXPECTED.items():
    actual = hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
    assert actual == digest, (name, actual)
with (root / 'vm1_1108.launch').open('x') as out:
    out.write(dt.datetime.now(dt.timezone.utc).isoformat() + '\n')
inner = root / 'vm1_1108_inner.py'
inner.write_text('''import pathlib, subprocess, sys, traceback, os, hashlib
root=pathlib.Path('/content/r4_s2')
try:
 for cmd in ([sys.executable,'-m','pip','install','-q','earth2studio[stormcast]==0.19.0'],[sys.executable,'-m','pip','install','-q','natten==0.21.6+torch2110cu130','-f','https://whl.natten.org']):
  print('INSTALL',cmd,flush=True); subprocess.run(cmd,check=True,timeout=900)
 import earth2studio,torch,natten
 print('ENV_OK',earth2studio.__version__,torch.__version__,torch.cuda.get_device_name(),flush=True)
 result=subprocess.run([sys.executable,'/content/r4_worker_v2.py'])
 (root/'vm1_1108.exit').write_text(str(result.returncode)+'\\n')
 print('WORKER_EXIT',result.returncode,flush=True)
 if result.returncode: raise RuntimeError('worker exit '+str(result.returncode))
except BaseException:
 print(traceback.format_exc(),flush=True)
 (root/'vm1_1108.failed').write_text(traceback.format_exc())
 raise
''')
env = os.environ.copy()
env.update(S2_START='0', S2_END='110', S2_MIN_FREE_GB='10')
log = (root / 'vm1_1108.log').open('a', buffering=1)
proc = subprocess.Popen([sys.executable, str(inner)], env=env, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print('R4_VM1_PID', proc.pid, 'START_UTC', dt.datetime.now(dt.timezone.utc).isoformat(), flush=True)
