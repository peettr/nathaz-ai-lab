#!/usr/bin/env python3
"""Metadata-only precheck; never request a full GRIB body.

Each Range request reads at most 16 bytes; THREDDS DDS/coordinate ASCII are
small metadata requests. Append-only JSONL checkpoint prevents lost evidence.
"""
import concurrent.futures as cf
import datetime as dt
import json
import pathlib
import re
import threading
import urllib.request
import urllib.error

ROOT=pathlib.Path(__file__).resolve().parent
EVENTS=json.loads((ROOT/'event_times_gc37.json').read_text())
OUT=ROOT/'INPUT_PRECHECK_2024.json'
LOG=ROOT/'INPUT_PRECHECK_2024_PROGRESS.jsonl'
LOCK=threading.Lock()
NAMES={'GHT':'Geopotential_height_isobaric','TT':'Temperature_isobaric',
       'UU':'u-component_of_wind_isobaric','VV':'v-component_of_wind_isobaric',
       'W':'Vertical_velocity_pressure_isobaric','RH':'Relative_humidity_isobaric',
       'Q':'Specific_humidity_isobaric'}
MIDDLE={12500,17500,22500,77500,82500,87500}
COMMON={100000,97500,95000,92500,90000,85000,80000,75000,70000,65000,60000,55000,50000,
        45000,40000,35000,30000,25000,20000,15000,10000,7000,5000,3000,2000,1000,700,500,300,200,100}
UPPER={100,200,300,500,700,1000,2000,3000,5000,7000}

def url(t, lead, b=False):
    stem='gfs.0p25'+('b' if b else '')
    name=f'{stem}.{t:%Y%m%d%H}.f{lead:03d}.grib2'
    dataset='d084003' if b else 'd084001'
    folder=f'{dataset}/{t:%Y}/{t:%Y%m%d}/{name}'
    return ('https://osdf-director.osg-htc.org/ncar/gdex/'+folder,
            'https://thredds.rda.ucar.edu/thredds/dodsC/files/g/'+folder)

def fetch(u,range_probe=False, timeout=75):
    headers={'User-Agent':'Mozilla/5.0 GC37 metadata-only prereg'}
    if range_probe:headers['Range']='bytes=0-15'
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=headers),timeout=timeout) as r:
            body=r.read(16 if range_probe else 180000)
            return {'url':u,'http':r.status,'content_range':r.headers.get('Content-Range'),
                    'sample':body[:16].hex() if range_probe else None},body
    except urllib.error.HTTPError as e:return {'url':u,'http':e.code,'error':str(e)},None
    except Exception as e:return {'url':u,'http':None,'error':str(e)},None

def parse_dds(body):
    text=body.decode('utf-8','replace')
    dims={}
    for label,name in NAMES.items():
        m=re.search(re.escape(name)+r'\[time\s*=\s*1\]\[(isobaric\d*)\s*=\s*(\d+)\]',text)
        dims[label]={'coord':m.group(1),'size':int(m.group(2))} if m else None
    extras={key:[line.strip() for line in text.splitlines() if key in line and '[time' in line][:8]
            for key in ('Precipitation', 'Temperature_height_above_ground','u-component_of_wind_height_above_ground',
                        'v-component_of_wind_height_above_ground')}
    return dims,extras

def levels(body):
    # OPeNDAP .ascii?isobaricN output has header and one numeric data row.
    text=body.decode('utf-8','replace')
    after=text.split('---------------------------------------------')[-1]
    vals=[]
    for token in re.findall(r'\b\d+(?:\.\d+)?\b',after):
        value=float(token)
        if 1<=value<=110000:vals.append(int(value))
    return sorted(set(vals))

def inspect(item):
    event,lead_name,role,t,n,b=item
    direct,thredds=url(t,n,b)
    range_status,header=fetch(direct,True,30)
    row={'event':event,'lead':lead_name,'role':role,'cycle_utc':t.isoformat(),
         'forecast_h':n,'dataset':'d084003' if b else 'd084001','range':range_status,
         'grib_header':header[:4].decode('ascii','replace') if header else None}
    if range_status['http']!=206 or row['grib_header']!='GRIB':
        row['metadata_status']='not_requested_file_absent_or_inaccessible'
    else:
        dds_resp,body=fetch(thredds+'.dds',timeout=75)
        row['dds']=dds_resp
        if body is not None:
            dims,extras=parse_dds(body)
            row['fields']=dims;row['surface_fields']=extras
            coordinates={}
            for c in sorted({v['coord'] for v in dims.values() if v}):
                response,values=fetch(thredds+'.ascii?'+c,timeout=75)
                coordinates[c]={'request':response,'levels_pa':levels(values) if values else None}
            row['coordinates']=coordinates
            row['pressure_field_levels_pa']={f:coordinates.get(v['coord'],{}).get('levels_pa') if v else None for f,v in dims.items()}
            if b:row['missing_middle_pa']={f:sorted(MIDDLE-set(row['pressure_field_levels_pa'].get(f) or [])) for f in ('GHT','TT','UU','VV','W','RH')}
            else:row['missing_common_pa']={f:sorted(COMMON-set(row['pressure_field_levels_pa'].get(f) or [])) for f in ('GHT','TT','UU','VV','RH')}
            row['missing_upper_w_pa']=sorted(UPPER-set(row['pressure_field_levels_pa'].get('W') or []))
            row['q_levels_pa']=row['pressure_field_levels_pa'].get('Q')
            row['rh_levels_pa']=row['pressure_field_levels_pa'].get('RH')
            row['apcp_0_6h_metadata_evidence']=[x for x in extras['Precipitation'] if ('6_hour' in x or '6_hour_accum' in x or '6hour' in x.lower())] if n==6 else None
            row['near_surface_metadata_evidence']={key:value for key,value in extras.items() if key!='Precipitation'}
        else:row['metadata_status']='dds_unavailable'
    with LOCK:
        with LOG.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    return row

def main():
    if OUT.exists() or LOG.exists():raise FileExistsError('never overwrite precheck outputs')
    jobs=[]
    for event in ('E2','E3','R1','R2'):
        e=EVENTS[event]
        for lead_name,detail in e['leads'].items():
            t=dt.datetime.fromisoformat(detail['t0'])
            end=dt.datetime.fromisoformat(e['end'])
            # Each required native analysis and precipitation source, both datasets at t0/t-6.
            for offset in (0,-6):
                for b in (False,True):jobs.append((event,lead_name,'analysis_t'+str(offset),t+dt.timedelta(hours=offset),0,b))
            for offset in (-6,-12):jobs.append((event,lead_name,'apcp_0_6h_t'+str(offset),t+dt.timedelta(hours=offset),6,False))
            k=0
            while t+dt.timedelta(hours=k)<=end:
                jobs.append((event,lead_name,'gfs_boundary',t,k,False));k+=6
    jobs=list(dict.fromkeys(jobs))
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        rows=list(pool.map(inspect,jobs))
    by={e:{lead:[] for lead in EVENTS[e]['leads']} for e in ('E2','E3','R1','R2')}
    for row in rows:by[row['event']][row['lead']].append(row)
    result={'checked_at_est':dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(),
            'method':'OSDF Range 0-15 + THREDDS DDS/coordinate ASCII; metadata only, not a decoded bitmap',
            'expected_common_levels_pa':sorted(COMMON,reverse=True),'expected_middle_pa':sorted(MIDDLE),
            'records':len(rows),'events':by}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    stats={e:{l:{'files':len(rs),'http206':sum(r['range']['http']==206 for r in rs),
                   'missing_or_unreadable':[f"{r['role']}:{r['dataset']}:{r['cycle_utc']}:f{r['forecast_h']:03d}" for r in rs
                                            if r['range']['http']!=206 or r.get('metadata_status')]} for l,rs in leads.items()}
           for e,leads in by.items()}
    (ROOT/'INPUT_PRECHECK_2024_SUMMARY.md').write_text('# 2024 GFS metadata-only precheck\n\n'+json.dumps(stats,ensure_ascii=False,indent=2)+'\n\nMetadata inventory cannot establish field bitmap/value completeness; uninspected/timeout is not proof of absence.\n')
    print('DONE',OUT,len(rows),json.dumps(stats,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
