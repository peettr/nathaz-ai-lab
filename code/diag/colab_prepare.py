import tarfile, hashlib, importlib.util, subprocess, sys, pathlib
p=pathlib.Path('/content/input_bundle.tar.gz')
print('bundle',hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
with tarfile.open(p) as tar: tar.extractall('/content',filter='data')
for name in ('climada','geopandas','shapely','xarray','scipy'):
 print(name, bool(importlib.util.find_spec(name)),flush=True)
if importlib.util.find_spec('climada') is None:
 subprocess.run([sys.executable,'-m','pip','install','-q','climada==6.1.0'],check=True)
print('ready',flush=True)
