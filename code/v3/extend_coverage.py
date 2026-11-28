import json,subprocess,time,hashlib
from pathlib import Path
p=Path('/content/l2613v3');d=json.loads((p/'coverage.json').read_text());x=next(x for x in d['building_files'] if '56397013_' in x)
assert x not in d['target_mesh_files'];print('extracting adjacent mesh',x,flush=True)
z=subprocess.run(['7z','x','-y',str(p/'niigata_2022.7z'),x,'-o'+str(p)],text=True,capture_output=True,timeout=600)
if z.returncode:raise RuntimeError(z.stdout[-1000:]+z.stderr[-1000:])
d['target_mesh_files'].append(x);q=p/x;d['extracted'].append({'path':x,'bytes':q.stat().st_size,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()});d['extended_at']=time.time()
(p/'coverage_adjacent.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(p/'coverage_adjacent.done').write_text('done');print('two meshes ready',flush=True)
