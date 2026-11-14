import subprocess,json,time,traceback
from pathlib import Path
p=Path('/content/l2613v3');out={'start':time.time(),'stages':{}}
try:
 assert json.loads((p/'generation.json').read_text())['gate_pass']
 for script in ['downstream_v3.py','export_stl_v3.py']:
  print('RUN',script,flush=True)
  z=subprocess.run(['python',str(p/script)],stdout=(p/(script+'.log')).open('xb'),stderr=subprocess.STDOUT,timeout=1800)
  out['stages'][script]=z.returncode
  if z.returncode:raise RuntimeError(script+' exit '+str(z.returncode))
  if script=='downstream_v3.py':
   d=json.loads((p/'downstream.json').read_text());assert not d.get('error'),d.get('error')
  print('DONE',script,flush=True)
except Exception as e:out['error']=repr(e);out['traceback']=traceback.format_exc();print('ERROR',repr(e),flush=True)
finally:
 out['end']=time.time();(p/'final_stage.json').write_text(json.dumps(out,indent=2));(p/'final_stage.done').write_text('done')
