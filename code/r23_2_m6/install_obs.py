from pathlib import Path
import tarfile,hashlib
p=Path('/content/m6/obs_source_20261028.tgz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='4eadad2fe1440e81b2ae1be4eb471adcca4294544452443b3b0d3988e732db22'
with tarfile.open(p) as t:
 assert all(x.name.startswith('obs/obs_') for x in t.getmembers())
 t.extractall('/content/m6',filter='data')
print('OBS_UPLOAD_SHA_OK',len(list(Path('/content/m6/obs').glob('obs_*.csv'))))
