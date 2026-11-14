import requests, subprocess, time, json, pathlib, hashlib, shutil
P=pathlib.Path('/content/l2613v3'); P.mkdir(exist_ok=True)
U='https://assets.cms.plateau.reearth.io/assets/2b/b5d503-a756-42bb-bbbe-8f6582847632/15100_niigata-shi_2022_citygml_1_op.7z'
D={'url':U,'start':time.time()}; (P/'coverage.json').write_text(json.dumps(D))
try:
 if not shutil.which('7z'):
  subprocess.run(['apt-get','update','-qq'],check=True,timeout=200)
  subprocess.run(['apt-get','install','-y','-qq','p7zip-full'],check=True,timeout=200)
 # Download only in ephemeral Colab; never persist the 3.5GB archive on 工作站.
 archive=P/'niigata_2022.7z'; h=hashlib.sha256()
 if not archive.exists():
  r=requests.get(U,stream=True,timeout=(30,180));r.raise_for_status();
  with archive.open('xb') as f:
   for chunk in r.iter_content(4*1024*1024):
    if chunk:f.write(chunk);h.update(chunk)
  D['sha256']=h.hexdigest()
 else:
  with archive.open('rb') as f:
   for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
  D['sha256']=h.hexdigest()
 D['bytes']=archive.stat().st_size; print('downloaded',D['bytes'],flush=True)
 listing=subprocess.run(['7z','l','-slt',str(archive)],text=True,capture_output=True,timeout=240,check=True).stdout
 paths=[line.split(' = ',1)[1] for line in listing.splitlines() if line.startswith('Path = ')]
 D['building_files']=[x for x in paths if '/bldg/' in x and x.endswith('.gml')]
 D['target_mesh_files']=[x for x in D['building_files'] if '56397014' in x]
 D['building_file_count']=len(D['building_files']); D['coverage']=bool(D['target_mesh_files'])
 print('COVERAGE',D['coverage'],'target',D['target_mesh_files'],'bldg count',len(D['building_files']),flush=True)
 if D['coverage']:
  for x in D['target_mesh_files']:
   z=subprocess.run(['7z','x','-y',str(archive),x,'-o'+str(P)],text=True,capture_output=True,timeout=500)
   if z.returncode:raise RuntimeError(z.stderr[-1000:]+z.stdout[-1000:])
  D['extracted']=[{'path':x,'bytes':(P/x).stat().st_size,'sha256':hashlib.sha256((P/x).read_bytes()).hexdigest()} for x in D['target_mesh_files']]
 D['end']=time.time()
except Exception as e:
 D['error']=repr(e);D['end']=time.time();print('ERROR',repr(e),flush=True)
finally:
 (P/'coverage.json').write_text(json.dumps(D,ensure_ascii=False,indent=2));(P/'coverage.done').write_text('done');print('COVERAGE_DONE',flush=True)
