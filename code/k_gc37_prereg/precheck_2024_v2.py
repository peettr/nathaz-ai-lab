#!/usr/bin/env python3
"""Metadata-only correction to 2024 inventory; never download full GRIB."""
import concurrent.futures as cf, datetime as dt, json, pathlib, re, time, urllib.request, urllib.error
import precheck_2024 as old
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'INPUT_PRECHECK_2024_v2.json'; SUMMARY=ROOT/'INPUT_PRECHECK_2024_v2_SUMMARY.md'
assert not OUT.exists() and not SUMMARY.exists(), 'preserve immutable result'
source=json.loads((ROOT/'INPUT_PRECHECK_2024.json').read_text())
rows=[r for leads in source['events'].values() for rs in leads.values() for r in rs]
def fetch(u,tries=3):
    statuses=[]
    for attempt in range(tries):
        status,body=old.fetch(u,timeout=35)
        statuses.append(status)
        if body is not None:return statuses,body
        if attempt+1<tries:time.sleep(1+attempt)
    return statuses,None
def ascii_values(b):
    if not b:return []
    text=b.decode('utf-8','replace').split('---------------------------------------------')[-1]
    return [float(x) for x in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?',text)]
def one(r):
    row={k:v for k,v in r.items() if k not in ('coordinates', 'pressure_field_levels_pa')}
    row['original_coordinates']=r.get('coordinates')
    cyc=dt.datetime.fromisoformat(r['cycle_utc'])
    _,url=old.url(cyc,r['forecast_h'],r['dataset']=='d084003')
    dds=None
    # Re-fetch only faulty/unavailable metadata; preserve successful earlier DDS evidence.
    if not r.get('fields') or any(v is None for v in r.get('fields',{}).values()) or r['role'].startswith('apcp'):
        status,dds=fetch(url+'.dds')
        row['v2_dds_attempts']=status
    else:row['v2_dds_attempts']='previous metadata usable'
    if dds:
        text=dds.decode('utf-8','replace')
        fields={}
        for short,name in old.NAMES.items():
            m=re.search(re.escape(name)+r'\[time\d*\s*=\s*1\]\[(isobaric\d*)\s*=\s*(\d+)\]',text)
            fields[short]={'coord':m.group(1),'size':int(m.group(2))} if m else None
        row['fields_v2']=fields
        names=re.findall(r'Float32\s+(Total_precipitation_surface_\d+_Hour_Accumulation)\[time(\d*)\s*=\s*1\]',text)
        row['apcp_names_v2']=names
        row['surface_dims_v2']={x:re.findall(r'Float32\s+'+re.escape(x)+r'\[time\d*\s*=\s*1\]\[(height_above_ground\d*)\s*=\s*(\d+)\]',text) for x in ('Temperature_height_above_ground','u-component_of_wind_height_above_ground','v-component_of_wind_height_above_ground')}
        coords=sorted({v['coord'] for v in fields.values() if v})
        row['coordinate_v2']={}
        for c in coords:
            prev=r.get('coordinates',{}).get(c,{})
            if prev.get('request',{}).get('http')==200 and prev.get('levels_pa'):
                level=[x for x in prev['levels_pa'] if x>=100]  # earlier parser included header dimension indices, but values are retained
                row['coordinate_v2'][c]={'levels_pa':level,'source':'previous ASCII; header indices excluded where <100'}
            else:
                sta,b=fetch(url+'.ascii?'+c)
                row['coordinate_v2'][c]={'attempts':sta,'levels_pa':[int(x) for x in ascii_values(b) if 100<=x<=110000] if b else None}
        for _,suffix in names:
            v='time'+suffix+'_bounds'; st,b=fetch(url+'.ascii?'+v)
            row.setdefault('apcp_bounds',{})[v]={'attempts':st,'values':ascii_values(b) if b else None}
        for field,pairs in row['surface_dims_v2'].items():
            for coord,_ in pairs:
                if coord not in row.setdefault('surface_height_coordinates',{}):
                    st,b=fetch(url+'.ascii?'+coord)
                    row['surface_height_coordinates'][coord]={'attempts':st,'values':ascii_values(b) if b else None}
    else:
        row['fields_v2']=r.get('fields')
        row['coordinate_v2']=r.get('coordinates')
        row['metadata_fallback']='DDS unavailable after three attempts; ASCII coordinate fallback only'
        for c in ('isobaric','isobaric1','isobaric2'):
            st,b=fetch(url+'.ascii?'+c,1)
            if b:row['coordinate_v2'][c]={'attempts':st,'levels_pa':[int(x) for x in ascii_values(b) if 100<=x<=110000]}
    levels={k:row.get('coordinate_v2',{}).get(v['coord'],{}).get('levels_pa') if v else None for k,v in (row.get('fields_v2') or {}).items()}
    required=('GHT','TT','UU','VV','RH')
    row['levels_status']={k:('pass' if set(old.MIDDLE if r['dataset']=='d084003' else old.COMMON).issubset(set(levels.get(k) or [])) else 'unverified') for k in required}
    row['levels_pa_v2']=levels
    if r['role'].startswith('apcp'):
        row['apcp_status']='pass_metadata_name' if row.get('apcp_names_v2') else 'unverified'
    return row
with cf.ThreadPoolExecutor(max_workers=6) as ex:
    revised=list(ex.map(one,rows))
by={e:{l:[] for l in source['events'][e]} for e in source['events']}
for r in revised:by[r['event']][r['lead']].append(r)
result={'checked_at_est':dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(),'method':'v2 corrected DDS timeN parser, bounded ASCII; immutable original inventory retained','events':by,'q_sample_status':'pending','records':len(revised)}
# Sample Q/RH with a single gridpoint and multiple levels using independently queried coordinates.
r=next(r for r in revised if r['event']=='E2' and r['lead']=='24h' and r['role']=='analysis_t0' and r['dataset']=='d084001')
_,u=old.url(dt.datetime.fromisoformat(r['cycle_utc']),0)
for var in ('Specific_humidity_isobaric','Relative_humidity_isobaric'):
    level=r['levels_pa_v2'].get('Q' if var.startswith('Specific') else 'RH') or []
    vals={}
    for pa in (85000,50000,10000,1000):
        if pa in level:
            ix=level.index(pa)
            st,b=fetch(u+f'.ascii?{var}[0:1:0][{ix}:1:{ix}][400:1:400][1000:1:1000]',1)
            vals[str(pa)]={'attempts':st,'values':ascii_values(b) if b else None}
    result.setdefault('q_rh_point_samples',{})[var]=vals
result['q_sample_status']='read_values_if_available_not_bitmap_proof'
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 2024 四事件输入预检 v2','',f'元数据逐文件：{OUT}；原始 JSON 保留未覆盖。Range 206 仅证明对象可访问，不证明 GRIB 位图完整。','']
for ev, leads in by.items():
    for lead,rs in leads.items():
        groups={}
        for typ,subset in [('分析',[r for r in rs if r['role'].startswith('analysis') and r['dataset']=='d084001']),('次级',[r for r in rs if r['role'].startswith('analysis') and r['dataset']=='d084003']),('降水',[r for r in rs if r['role'].startswith('apcp')]),('边界',[r for r in rs if r['role']=='gfs_boundary'])]:
            fail=[f"{r['cycle_utc']} f{r['forecast_h']:03d}:"+(','.join(k for k,v in r['levels_status'].items() if v!='pass') if typ!='降水' else r.get('apcp_status','unverified')) for r in subset if r['range']['http']!=206 or (r.get('apcp_status')!='pass_metadata_name' if typ=='降水' else any(v!='pass' for v in r['levels_status'].values()))]
            groups[typ]='元数据通过' if not fail and subset else '未核实 '+str(len(fail))+'：'+';'.join(fail)
        lines.append(f"{ev} {lead} | "+' | '.join(f'{k} {v}' for k,v in groups.items()))
lines+=['','Q/RH 单点见 JSON q_rh_point_samples；0–6 h 累计时间区间及 2/10 m 坐标需以 time bounds/坐标请求核对；不可把访问性视为物理完整性。']
SUMMARY.write_text('\n'.join(lines)+'\n')
print('DONE',OUT,SUMMARY,len(revised),flush=True)
