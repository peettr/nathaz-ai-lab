from pathlib import Path
import sys,json,hashlib,zipfile,time
r=Path('/content/r216_caseA_0b');out=r/'out';files=[p for p in out.glob('*') if p.is_file() and p.suffix in ('.json','.log')]+[r/'run.log',r/'failed',r/'EXPERIMENT_CARD.md']
manifest={p.relative_to(r).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mtime':p.stat().st_mtime} for p in files}
(out/'manifest.json').write_text(json.dumps({'files':manifest,'session_start':float(Path('/content/r216_session_start').read_text()),'pack_time':time.time()},indent=2))
with zipfile.ZipFile(out/'deliverables.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[out/'manifest.json']:z.write(p,p.relative_to(r))
print('PACKAGE',out/'deliverables.zip',(out/'deliverables.zip').stat().st_size,'sha256',hashlib.sha256((out/'deliverables.zip').read_bytes()).hexdigest())
