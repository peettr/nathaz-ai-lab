from pathlib import Path
import tarfile,hashlib
r=Path('/content/m5'); files=sorted((r/'paris_gfs').glob('*.csv'))
assert len(files)==1104
out=r/'paris_gfs_complete_1104.tgz'
with tarfile.open(out,'w:gz') as t:
 for f in files:t.add(f,arcname='paris_gfs/'+f.name)
print(len(files),out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
