#!/usr/bin/env python3
"""Decode every required 2024 GDEX GRIB on Colab before any inference.
Reports are incremental, immutable at completion; no substitution of inputs.
"""
import argparse, datetime as dt, hashlib, json, pathlib, time
import numpy as np
import pygrib
from prepare_gc37_gfs_2024_e2e3_v2 import download, url
from apcp_identical_v2 import select_identical_apcp

LEVELS=(1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1)
MID=(125,175,225,775,825,875)
FIVE=('gh','t','u','v','r')
ROOT=pathlib.Path('/content/r234c_gc37_E2E3')
EVENTS=json.loads(pathlib.Path('/content/event_times_gc37.json').read_text())
CROP={'E2':(slice(148,265),slice(948,1141)), 'E3':(slice(128,245),slice(968,1177))}  # north-to-south lat / 0..360 lon

def expected():
    objects={}; cycle_index={}
    for event in ('E2','E3'):
        for lead,spec in EVENTS[event]['leads'].items():
            t0=dt.datetime.fromisoformat(spec['t0']); end=dt.datetime.fromisoformat(EVENTS[event]['end'])
            keys=[]
            for t in (t0-dt.timedelta(hours=6),t0):
                for ds in ('d084001','d084003'):
                    k=(ds,t,0); objects[k]=url(*k); keys.append(k)
                k=('d084001',t-dt.timedelta(hours=6),6); objects[k]=url(*k); keys.append(k)
            for h in range(6,int((end-t0).total_seconds()/3600)+1,6):
                k=('d084001',t0,h); objects[k]=url(*k); keys.append(k)
            cycle_index[f'{event}_{lead}']=[str_key(k) for k in keys]
    return objects,cycle_index

def str_key(k): return f'{k[0]}_{k[1]:%Y%m%d%H}_f{k[2]:03d}'

def inspect(k,path,events):
    ds,t,h=k; rec={'key':str_key(k),'url':url(*k),'bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),'checked_events':sorted(events),'fields':{},'errors':[]}
    grb=pygrib.open(str(path))
    try:
        actual={}; levels=MID if ds=='d084003' else LEVELS
        for short in (*FIVE,'q') if ds=='d084001' else FIVE:
            # For d084003 only RH among humidities; d084001 Q is the AI native initial source.
            for p in levels:
                matches=grb.select(shortName=short,typeOfLevel='isobaricInhPa',level=p)
                if len(matches)!=1:
                    rec['errors'].append(f'{short}_{p}:messages={len(matches)}');continue
                m=matches[0]; a=m.values
                if np.ma.isMaskedArray(a):a=a.filled(np.nan)
                a=np.asarray(a); finite=np.isfinite(a)
                # Both pre-registered event crops; assert every value on both domains.
                for event in events:
                    sl=CROP[event]; cut=finite[sl]
                    if not cut.all(): rec['errors'].append(f'{event}:{short}_{p}:nonfinite={int((~cut).sum())}')
                actual.setdefault(short,[]).append(p)
        if ds=='d084003':
            for p in MID:
                matches=grb.select(shortName='w',typeOfLevel='isobaricInhPa',level=p)
                if len(matches)!=1:rec['errors'].append(f'w_{p}:messages={len(matches)}');continue
                a=matches[0].values
                if np.ma.isMaskedArray(a):a=a.filled(np.nan)
                for event in events:
                    if not np.isfinite(np.asarray(a)[CROP[event]]).all():rec['errors'].append(f'{event}:w_{p}:nonfinite')
                actual.setdefault('w',[]).append(p)
        else:
            for short in ('2t','10u','10v'):
                matches=grb.select(shortName=short)
                if len(matches)!=1:rec['errors'].append(f'{short}:messages={len(matches)}');continue
                m=matches[0]; a=m.values
                if np.ma.isMaskedArray(a):a=a.filled(np.nan)
                for event in events:
                    if not np.isfinite(np.asarray(a)[CROP[event]]).all():rec['errors'].append(f'{event}:{short}:nonfinite')
                actual[short]=[{'level':int(m.level),'type':str(m.typeOfLevel)}]
            if h==6 and t in precip_times:
                matches=[m for m in grb.select(shortName='tp',typeOfLevel='surface') if str(m.stepRange) in ('0-6','6')]
                try:m,dedup=select_identical_apcp(matches)
                except ValueError as exc:rec['errors'].append(str(exc))
                else:
                    rec['apcp_dedup']=dedup
                    a=m.values
                    if np.ma.isMaskedArray(a):a=a.filled(np.nan)
                    for event in events:
                        if not np.isfinite(np.asarray(a)[CROP[event]]).all():rec['errors'].append(f'{event}:APCP:nonfinite')
                    actual['APCP']=[{'stepRange':str(m.stepRange),'units':str(m.units)}]
        rec['fields']=actual
    finally: grb.close()
    rec['ok']=not rec['errors']
    return rec

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(ROOT));a=ap.parse_args()
    root=pathlib.Path(a.root);root.mkdir(parents=True,exist_ok=True)
    objects,cycles=expected()
    precip_times={k[1] for keys in cycles.values() for token in keys for k in objects if str_key(k)==token and k[0]=='d084001' and k[2]==6 and token in keys}
    refs={str_key(k):{event for event in ('E2','E3') if any(str_key(k) in keys for name,keys in cycles.items() if name.startswith(event+'_'))} for k in objects}
    report=root/'INPUT_NUMERIC_GATE_E2E3_V2.jsonl'
    if report.exists():raise FileExistsError(report)
    print('GATE_START',len(objects),'unique_files',flush=True)
    with report.open('x') as fh:
        for i,(k,u) in enumerate(objects.items(),1):
            key=str_key(k); name=u.rsplit('/',1)[-1];target=root/'raw'/name;target.parent.mkdir(exist_ok=True)
            try:
                meta=download(u,target)
                rec=inspect(k,target,refs[key]);rec['download']=meta
            except Exception as exc:
                rec={'key':key,'url':u,'ok':False,'errors':[f'{type(exc).__name__}: {exc}']}
            fh.write(json.dumps(rec)+'\n');fh.flush()
            print('GATE_FILE',i,len(objects),key,'OK' if rec['ok'] else 'FAIL',rec['errors'][:3],flush=True)
            if not rec['ok']:break
    rows=[json.loads(x) for x in report.read_text().splitlines()]
    summary={'expected_files':len(objects),'examined_files':len(rows),'all_pass':len(rows)==len(objects) and all(x['ok'] for x in rows),'dedup_identical':sum(x.get('apcp_dedup',{}).get('dedup_identical',0) for x in rows),'cycle_keys':cycles,'failures':[x for x in rows if not x['ok']]}
    (root/'INPUT_NUMERIC_GATE_E2E3_V2_SUMMARY.json').write_text(json.dumps(summary,indent=2))
    if not summary['all_pass']:raise SystemExit('INPUT_GATE_FAILED: no inference authorized')
    (root/'INPUT_NUMERIC_GATE_E2E3_V2.passed').write_text('PASS\n')
    print('INPUT_GATE_PASSED',len(rows),flush=True)
