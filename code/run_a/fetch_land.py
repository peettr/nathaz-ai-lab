from pathlib import Path
import urllib.request,hashlib
u='https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip'
p=Path('/content/ne_10m_land.zip')
with urllib.request.urlopen(u,timeout=60) as r:p.write_bytes(r.read())
print(u,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
