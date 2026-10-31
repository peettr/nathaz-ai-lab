import csv,gzip,json,urllib.request,hashlib,collections
from pathlib import Path
p=Path('/content'); manifest=json.loads((p/'manifest_v2.json').read_text()); data={}
for entry in manifest['best']:
    b=urllib.request.urlopen(entry['url'],timeout=60).read()
    assert hashlib.sha256(b).hexdigest()==entry['sha256'],entry['event']
    for line in gzip.decompress(b).decode().splitlines():
        a=[x.strip() for x in line.split(',')]
        if len(a)<20 or a[4]!='BEST':continue
        try: value=float(a[19])
        except ValueError:continue
        data.setdefault((entry['event'],a[2]),value)
rows=list(csv.DictReader((p/'tracks.csv').open())); matched=collections.Counter()
for r in rows:
    t=r['time_utc'][:10].replace('-','')+r['time_utc'][11:13]
    v=data.get((r['event'],t),None)
    r['bdeck_rmw_nmi']=v if v and 5<=v<=200 else ''
    if r['bdeck_rmw_nmi']:matched[r['event']]+=1
with (p/'tracks_v3.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
print('bdeck',len(rows),sum(matched.values()),dict(matched),flush=True)
url='https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip'
b=urllib.request.urlopen(url,timeout=120).read()
(p/'ne_10m_land.zip').write_bytes(b)
print('land',len(b),hashlib.sha256(b).hexdigest(),flush=True)
