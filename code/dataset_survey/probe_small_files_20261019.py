import json, urllib.request, io, zipfile, re
from pathlib import Path
base=Path(__file__).parent
records=json.loads((base/'zenodo_file_audit_20261019.json').read_text())+json.loads((base/'zenodo_observation_audit_20261019.json').read_text())
ids={15401456,15429018,15429872,10655033,14761503,15521893}
entries=[]
for rec in records:
 if rec['id'] not in ids: continue
 for f in rec['files']:
  name=f['name']
  if not (name.lower().endswith(('.md','.csv','.zip')) and f['size']<55000000):continue
  if rec['id']==14761503 and name!='paris-harmonised-dwl-morrison-fork.zip':continue
  if rec['id']==15521893 and name!='2016-London-L1-MNH.zip':continue
  if rec['id']==10655033 and name not in ('Meteo-mast_PVK_measurement_TURDATA.zip','Meteo_data_Prague_MS_TURDATA.zip'):continue
  o={'id':rec['id'],'name':name,'url':f['url']}
  try:
   req=urllib.request.Request(f['url'],headers={'User-Agent':'ResearchDatasetAudit/1.0'})
   with urllib.request.urlopen(req,timeout=40) as resp:b=resp.read(55000000)
   if name.lower().endswith('.zip'):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
     o['count']=len(z.infolist());o['members']=[{'name':i.filename,'size':i.file_size} for i in z.infolist()][:35]
     for i in z.infolist():
      if i.file_size<15000 and i.filename.lower().endswith(('.txt','.csv','.md')):
       o.setdefault('headers',{})[i.filename]=z.read(i)[:650].decode('utf8','replace')
   else:o['header']=b[:1600].decode('utf8','replace')
  except Exception as e:o['error']=str(e)[:200]
  entries.append(o)
  print(rec['id'],name,o.get('error','ok'),flush=True)
p=base/'small_file_probes_20261019.json';p.write_text(json.dumps(entries,ensure_ascii=False,indent=2));print(p)
