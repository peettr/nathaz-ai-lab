"""Read archived IEM/ISD bytes; only new Q5 candidate days may require ISD."""
import csv,io,json,gzip,tarfile,urllib.request,datetime as dt,os
from pathlib import Path
KEYS=set(); ROOT=None; CORE=None; INDEX={}; ISD_INDEX={}; NEW_ISD=[]
def setup(core,root):
 global ROOT,CORE,KEYS,INDEX,ISD_INDEX
 ROOT=root;CORE=core
 KEYS={(st,int(y)) for st,y in json.loads((root/'selected_keys.json').read_text())}
 INDEX={}
 with tarfile.open(root/'source_stage.tar') as t:
  for f in t:
   if f.name.startswith('iem/'):
    st,y=f.name.split('/')[-1].replace('.gz','').split('_')
    INDEX[st,int(y)]=gzip.decompress(t.extractfile(f).read()).decode('utf-8','replace')
   elif f.name.startswith('isd/'):
    ISD_INDEX[f.name.split('/')[-1]]=gzip.decompress(t.extractfile(f).read())
 receipts=[json.loads(x) for x in (root/'tacc_raw_receipts.jsonl').read_text().splitlines()]
 mapping={r['url']:Path(r['file']).name for r in receipts if r['kind']=='isd'}
 def load_obs(st,y):
  rows=list(csv.DictReader(io.StringIO(INDEX[st,y])))
  original=json.loads((root/'final2_qc.json').read_text())[st+'_'+str(y)]
  a=dt.datetime(y,10,1);b=dt.datetime(y+1,4,1)
  reports=[];candidates=[]
  for r in rows:
   t=core.parse(r.get('valid',''))
   if not t or not a<=t<b:continue
   raw=r.get('metar') or ''
   regular=not raw.startswith('SPECI ') and (' '+st+' ' in ' '+raw+' ' or raw.startswith(st+' '))
   reports.append({'time':t,'raw':raw,'wx':r.get('wxcodes') or '', 'regular':regular})
   for key,src in [('gust','gust'),('peak_wind_gust','pk')]:
    v=core.num(r.get(key))
    if v is None:continue
    et=core.peak_time(r) if src=='pk' else t
    if et is None or not a<=et<b:continue
    candidates.append({'time':et,'value':v,'source':src,'report_time':t,'raw':raw})
  reports.sort(key=lambda r:r['time'])
  cs=sorted(candidates,key=lambda c:(-c['value'],c['time']))
  if cs and original['original_peak']:
   z=original['original_peak'];assert cs[0]['value']==z['kn'] and core.stamp(cs[0]['time'])==z['event_utc'],(st,y,z,cs[0])
  return {'st':st,'y':y,'reports':reports,'candidates':candidates,'coverage':original['coverage'],'url':original['metar_url']}
 core.load_obs=load_obs
 global isd_response
 def isd_response(url):
  name=mapping.get(url)
  if name in ISD_INDEX:return ISD_INDEX[name]
  req=urllib.request.Request(url,headers={'User-Agent':'PETW-station-noQ3-sensitivity/1.0'})
  with urllib.request.urlopen(req,timeout=60) as response:raw=response.read()
  NEW_ISD.append({'url':url,'bytes':len(raw)})
  (root/'new_isd_requests.json').write_text(json.dumps(NEW_ISD,indent=2))
  return raw
 globals()['isd_response']=isd_response
