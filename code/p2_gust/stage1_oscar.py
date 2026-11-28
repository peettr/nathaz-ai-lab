#!/usr/bin/env python3
"""Extract dated wind-speed sensor AGL metadata from OSCAR/WIGOS XML, separately from frozen roster."""
import csv,hashlib,json,xml.etree.ElementTree as ET,datetime as dt,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
R=Path('/content/p1');NS={'om':'http://www.opengis.net/om/2.0','wmdr':'http://def.wmo.int/wmdr/2017','gml':'http://www.opengis.net/gml/3.2'}
HREF='{http://www.w3.org/1999/xlink}href'

def one(s):
    sid=s['station'];wid=s['wigos_id'];url='https://oscar.wmo.int/surface/rest/api/wmd/download/'+wid
    out={'station':sid,'wigos_id':wid,'source_url':url,'height_m':'','deployment_begin':'','status':'missing'}
    try:
        if not wid:raise ValueError('no station_wigos_id')
        r=requests.get(url,timeout=40);r.raise_for_status()
        xml=ET.fromstring(r.content);out['source_sha256']=hashlib.sha256(r.content).hexdigest()
        candidates=[]
        for o in xml.iter():
            if o.tag.split('}')[-1]!='observation':continue
            props={p.get(HREF) for p in o.iter() if p.tag.split('}')[-1]=='observedProperty'}
            if 'http://codes.wmo.int/wmdr/ObservedVariableAtmosphere/12006' not in props:continue
            for dep in o.iter():
                if dep.tag.split('}')[-1]!='Deployment':continue
                h=dep.find('./wmdr:heightAboveLocalReferenceSurface',NS)
                ref=dep.find('./wmdr:localReferenceSurface',NS)
                begin=dep.find('./wmdr:validPeriod/gml:TimePeriod/gml:beginPosition',NS)
                end=dep.find('./wmdr:validPeriod/gml:TimePeriod/gml:endPosition',NS)
                if h is not None and h.text and ref is not None and (ref.get(HREF) or '').endswith('/localGround'):
                    candidates.append((float(h.text),begin.text if begin is not None else None,end.text if end is not None else None))
        candidates=list(dict.fromkeys(candidates));out['candidates']=candidates
        # Require unchanged height over entire verification span; different dated heights remain missing.
        viable=[x for x in candidates if x[1] and x[1][:10]<='2022-10-01' and (not x[2] or x[2][:10]>='2025-04-01')]
        unique={x[0] for x in viable}
        if len(unique)==1:
            best=sorted(viable,key=lambda x:x[1])[-1];out.update(height_m=best[0],deployment_begin=best[1],status='verified_full_period')
        elif len(unique)>1:out['status']='conflicting_active_heights'
        else:out['status']='no_full_period_deployment'
    except Exception as e:out['status']='fetch_or_parse_failed';out['error']=repr(e)
    print('OSCAR',sid,out['status'],out['height_m'],flush=True)
    return out

def main():
    p=R/'stations_p2_frozen.csv';m=json.loads((R/'freeze_manifest.json').read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest()==m['station_sha256']
    stations=list(csv.DictReader(p.open()))
    with ThreadPoolExecutor(max_workers=6) as pool:
        result=sorted((x.result() for x in as_completed([pool.submit(one,s) for s in stations])),key=lambda x:x['station'])
    with (R/'oscar_height_metadata.csv').open('x',newline='') as f:
        cols=['station','wigos_id','height_m','deployment_begin','status','source_url','source_sha256','candidates','error'];w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for x in result:w.writerow({**x,'candidates':json.dumps(x.get('candidates',[]))})
    print('OSCAR_DONE',len(result),sum(x['status']=='verified_full_period' for x in result),flush=True)
if __name__=='__main__':main()
