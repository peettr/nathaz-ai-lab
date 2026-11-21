import os,subprocess,time,traceback,pathlib,json,hashlib
base=pathlib.Path('/content'); log=base/'diag_run.log'
try:
 def run(cmd):
  print('CMD',cmd,flush=True)
  p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  print(p.stdout[-16000:],flush=True)
  if p.returncode:raise RuntimeError(f'command exit {p.returncode}: {cmd}')
 run(['uv','venv','/content/diagvenv3','--python','/usr/bin/python3.12'])
 run(['uv','pip','install','--python','/content/diagvenv3/bin/python','climada==6.1.0','gdal==3.8.4','geopandas','shapely','xarray','numpy<2'])
 run(['/content/diagvenv3/bin/python','/content/diag_inputs.py','--out','/content/diagout'])
 print('OUTPUTS',[(p.name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((base/'diagout').iterdir())],flush=True)
 (base/'diag_run.done').write_text('success\n')
except Exception:
 traceback.print_exc()
 (base/'diag_run.failed').write_text(traceback.format_exc())
