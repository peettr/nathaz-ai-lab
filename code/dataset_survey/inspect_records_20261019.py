import json, urllib.request, urllib.error, re, io, zipfile, hashlib
from pathlib import Path
ids=[12749995,11394347,7075696,10656886,19041698,15401456,15429018,15429872]
out=[]
def get(url, headers=None, maxread=200000):
    req=urllib.request.Request(url,headers={'User-Agent':'ResearchDatasetAudit/1.0',**(headers or {})})
    with urllib.request.urlopen(req,timeout=35) as r:
        return r.status,dict(r.headers),r.read(maxread+1)
for rid in ids:
    rec={'id':rid,'url':f'https://zenodo.org/api/records/{rid}'}
    try:
        _,_,b=get(rec['url'],maxread=300000)
        j=json.loads(b)
        m=j['metadata']; rec.update(title=m.get('title'),description=re.sub('<[^>]+>',' ',m.get('description','')),license=m.get('license'),files=[])
        for f in j.get('files',[]):
            item={'name':f['key'],'size':f['size'],'checksum':f.get('checksum'),'url':f['links'].get('self')}
            if item['size'] <= 60000000 and item['name'].lower().endswith(('.zip','.py')):
                try:
                    st,h,data=get(item['url'],maxread=60000000)
                    item['http_status']=st
                    if item['name'].endswith('.zip') and len(data)==item['size']:
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            item['zip_entries']=[{'name':x.filename,'size':x.file_size} for x in z.infolist()][:100]
                            item['zip_count']=len(z.infolist())
                            item['zip_headers']={n:z.read(n)[:350].decode('utf8','replace') for n in z.namelist() if n.lower().endswith(('.csv','.txt','.md','.json','.py')) and z.getinfo(n).file_size<10000 and not n.startswith('__MACOSX')}
                    elif item['name'].endswith('.py'): item['header']=data[:1300].decode('utf8','replace')
                except Exception as e:item['probe_error']=str(e)[:200]
            elif item['size']>60000000 and item['name'].lower().endswith(('.zip','.h5','.hdf5','.nc')):
                try:
                    st,h,data=get(item['url'],{'Range':'bytes=0-511'},maxread=1024)
                    item['range_probe']={'status':st,'content_range':h.get('Content-Range'),'length_read':len(data),'magic':data[:16].hex()}
                except Exception as e:item['range_error']=str(e)[:200]
            rec['files'].append(item)
    except Exception as e:rec['error']=str(e)[:300]
    out.append(rec)
    print(rid,rec.get('title'),len(rec.get('files',[])),rec.get('error'),flush=True)
p=Path(__file__).with_name('zenodo_file_audit_20261019.json')
p.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(p)
