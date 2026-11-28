import requests, pathlib, zipfile, hashlib, json, csv, io
R=pathlib.Path('/content/l2628d1');R.mkdir(exist_ok=True)
rec=requests.get('https://zenodo.org/api/records/19205784',timeout=45).json(); f=rec['files'][0]
p=R/'zenodo.zip'
if not p.exists():
 with requests.get(f['links']['self'],stream=True,timeout=(30,120)) as r:
  print('ZIP_STATUS',r.status_code,flush=True);r.raise_for_status()
  with p.open('xb') as o:
   for b in r.iter_content(1024*1024):o.write(b)
assert hashlib.sha256(p.read_bytes()).hexdigest()=='38291861f6ab5e025e63661c4089febb53f5b46977b2ff0901ccadc26971d65d'
with zipfile.ZipFile(p) as z:
 for m in z.namelist():
  if ('predicted outputs/test_TCs/intensity/data/' in m and m.endswith('.csv')) or ('predicted outputs/test_TCs/structure/data_day/' in m and m.endswith('.csv')):
   t=R/'selected'/m;t.parent.mkdir(parents=True,exist_ok=True)
   with t.open('xb') as o:o.write(z.read(m))
files=list((R/'selected').rglob('*.csv'))
for p in files:
 if 'structure/data_day/1d/' in str(p) and 'lq_' in p.name:
  print('STRUCT_EXAMPLE',p.relative_to(R),p.read_text()[:500],flush=True);break
print('FILES',len(files),flush=True)
url='https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv'
p=R/'ibtracs.csv'
with requests.get(url,stream=True,timeout=(30,120)) as r:
 print('IB_STATUS',r.status_code,flush=True);r.raise_for_status()
 with p.open('xb') as o:
  for b in r.iter_content(1024*1024):o.write(b)
print('IB_SHA256',hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print('STAGE_DONE',flush=True)
