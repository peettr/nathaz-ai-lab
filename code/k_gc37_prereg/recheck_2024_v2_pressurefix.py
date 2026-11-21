#!/usr/bin/env python3
"""Correct Q/RH coordinate-index audit without modifying prior evidence."""
import json, pathlib, re, urllib.parse, urllib.request, urllib.error, concurrent.futures
B=pathlib.Path(__file__).resolve().parent
old=json.loads((B/'INPUT_PRECHECK_2024_v2_RECHECK.json').read_text())
assert not (B/'INPUT_PRECHECK_2024_v2_PRESSUREFIX.json').exists()
base='https://thredds.rda.ucar.edu/thredds/dodsC/files/g/d084001/2024/20240518/gfs.0p25.2024051818.f000.grib2.ascii?'
def request(q):
 url=base+urllib.parse.quote(q,safe='')
 try:
  with urllib.request.urlopen(url,timeout=25) as r:return {'http':r.status,'text':r.read(10000).decode(),'url':url}
 except Exception as e:return {'http':getattr(e,'code',None),'error':str(e),'url':url}
r=request('isobaric')
assert r['http']==200,r
body=r['text'].split('---------------------------------------------',1)[1]
coords=[int(float(x)) for x in re.findall(r'\d+(?:\.\d+)?',body.split('\n',2)[2])]
assert len(coords)==41 and coords[0]==1 and coords[-1]==100000,coords
report={'note':'Corrects prior sample-index bug: old script filtered levels below 100 Pa before indexing; prior Q/RH labels were wrong. This file does not overwrite the old evidence.', 'coordinate_url':r['url'],'coordinate_pa':coords,'samples':{}}
def sample(args):
 var,pa=args;idx=coords.index(pa)
 a=request(f'{var}[0:1:0][{idx}:1:{idx}][300:1:300][1000:1:1000]')
 text=a.get('text','')
 m=re.search(r'^\[0\]\[0\]\[0\],\s*([^\s]+)',text,re.M)
 c=re.search(r'isobaric\[1\]\s*\n([^\s]+)',text)
 return (var,pa,{'http':a['http'],'url':a['url'],'index':idx,'value':float(m.group(1)) if m else None,'reported_pressure_pa':float(c.group(1)) if c else None,'error':a.get('error')})
args=[(v,p) for v in ('Specific_humidity_isobaric','Relative_humidity_isobaric') for p in (85000,50000,10000,1000)]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for v,p,s in pool.map(sample,args):report['samples'].setdefault(v,{})[str(p)]=s
for v,table in report['samples'].items():
 for k,s in table.items():
  assert s['http']==200 and s['reported_pressure_pa']==int(k) and s['value'] is not None,(v,k,s)
path=B/'INPUT_PRECHECK_2024_v2_PRESSUREFIX.json'
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(path)
print({v:{k:(s['value'],s['reported_pressure_pa']) for k,s in d.items()} for v,d in report['samples'].items()})