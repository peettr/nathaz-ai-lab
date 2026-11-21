from pathlib import Path
import runpy,hashlib,json,time
r=Path('/content/luw-aij-caseA-turb-20261014')
runpy.run_path('/content/extract_r9.py',run_name='__main__')
files=['samples_caseA_r9_2m.json','solver.log','solver.exit','solver.metrics']
manifest={}
for name in files:
 p=r/name;assert p.exists() and p.stat().st_size>0,name
 manifest[name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime':time.strftime('%m-%d %H:%M:%S %Z',time.localtime(p.stat().st_mtime))}
(r/'remote_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2),flush=True)
