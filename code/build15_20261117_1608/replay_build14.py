import controller as c
import json, pathlib, tempfile
from unittest.mock import patch

old=c.R.parent/'build14_20261117_1545'
raw=json.loads(next(line for line in (old/'attempt_01/events.jsonl').read_text().splitlines() if json.loads(line)['event']=='machine'))['output']
fixture=next(c.R.parent.glob('build5_*/evidence/channel_x_off.log')).read_text(errors='replace')
assert 'MemAvailable:' in raw and 'GPU_MACHINE ' not in raw
for scenario in ('raw_then_terminal','raw_then_timeout','gpu_recovered','gpu_low'):
 with tempfile.TemporaryDirectory(dir=c.R) as z:
  d=pathlib.Path(z); seen=[]; stamp=c.time.time()
  def call(args,limit=30):
   if 'exec' in args:
    script=pathlib.Path(args[-1]).name;seen.append(script)
    if script=='machine.py':
     if scenario in ('gpu_recovered','gpu_low') and seen.count(script)==2:
      free=12000 if scenario=='gpu_low' else 40000
      return 0,raw+'\nGPU_MACHINE '+json.dumps(dict(rc=0,stdout=f'NVIDIA A100, 40960, {free}\n',stderr=''))
     return 0,raw
    if script=='launch_gate.py':return 124,'client timeout (fixture)'
    if script=='probe_gate.py':
     if scenario=='raw_then_timeout' and seen.count(script)==1:return 124,'client timeout (fixture)'
     return 0,'PROBE '+json.dumps(dict(alive=False,log='',done=False,failed=True,b_passed=False,ready={}))
   if 'stop' in args:seen.append('stop')
   return 0,''
  with patch.object(c,'call',call),patch.object(c.time,'sleep',lambda _:None):
   c.work(d,'fixture','gpu-a100-fixture',stamp,d/'sessions.json')
  events=[json.loads(x)['event'] for x in (d/'events.jsonl').read_text().splitlines()]
  if scenario.startswith('raw_'):
   assert seen.count('machine.py')==3 and 'machine_fallback' in events and 'launch_gate.py' in seen,seen
   assert seen.index('stop')>seen.index('probe_gate.py'),seen
   if scenario=='raw_then_timeout':assert seen.count('probe_gate.py')==2,seen
  elif scenario=='gpu_low':assert seen.count('machine.py')==2 and 'launch_gate.py' not in seen,seen
  else:assert seen.count('machine.py')==2 and 'launch_gate.py' in seen and 'machine_fallback' not in events,seen
  print('PASS',scenario,seen)
assert c.solver_device(fixture)['vram_reported_mb']==97250
print('PASS solver device parser with archived real log; not Build15 hardware evidence')
