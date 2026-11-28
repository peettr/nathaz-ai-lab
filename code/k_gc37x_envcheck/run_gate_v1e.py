#!/usr/bin/env python3
"""Bounded frontend validation of existing immutable WPS fixtures and +0 h pairs."""
import sys, json, pathlib, hashlib, contextlib, io, warnings
import numpy as np
from metpy.calc import most_unstable_parcel, mixed_parcel, lcl, dewpoint_from_specific_humidity
from metpy.units import units
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
E=R/'envcheck_v1'
sys.path.insert(0,str(E))
import envcheck_gc37x_v1e as m
raw=json.loads((E/'VALIDITY_GATE_v1b_windfix_raw_20261127.json').read_text())
config=R/'inputs_N1N3N4_v1/event_times_bbox_gc37x.json'
out={'script':str(E/'envcheck_gc37x_v1e.py'),'metpy_version':m.metpy.__version__,'known_answer':None,'fixtures':[],'fields':[],'flat13024':None,'t0':[]}
with contextlib.redirect_stdout(io.StringIO()): m.known_answer()
s=io.StringIO()
with contextlib.redirect_stdout(s): m.known_answer()
out['known_answer']=json.loads(s.getvalue())
for row in raw['fixtures']:
    case=row['case']; path=pathlib.Path(row['file']); report=pathlib.Path(row['report'])
    result=m.assess(path,'N1','2024061418',report,config,True,1)
    out['fixtures'].append({'case':case,'file':str(path),'report':str(report),'report_sha256':m.sha(report), 'output':result})
    print('FIXTURE',case,json.dumps(result,ensure_ascii=False),flush=True)
for row in raw['fields']:
    path=pathlib.Path(row['file']); cfg=json.loads(config.read_text())['events']['N1']
    idx=m.mask_points(path,float(cfg['lat']),float(cfg['lon']))
    fields,_=m.records(path)
    try: qc=m.field_qc(fields,idx,True); status='pass'
    except ValueError as e: qc={'error':str(e)}; status='fail'
    out['fields'].append({'file':str(path),'min_adjacent_correlation':qc,'qc':status,'grid_count':len(idx)})
    print('FIELD',len(out['fields']),status,str(path),flush=True)
# First characterize the exact flat-index parcel without extrapolating its result.
path=R/'drivers_N1_v1/GFS/2024061418/FILE:2024-06-14_18'
fields,_=m.records(path, [13024]); p=np.array(m.LEVELS,dtype=float)
col={key:np.array([fields[key,100*lev][0] for lev in m.LEVELS]) for key in m.FIELDS}
soil=fields['SOILHGT',200100][0]; z=col['GHT']; ps=m.surface_pressure(p,z,soil)
mask=(p<ps)&(z>soil)&(p>=100); pp=p[mask]*units.hPa; tt=col['TT'][mask]*units.K
Td=dewpoint_from_specific_humidity(pp,tt,np.maximum(col['SPECHUMD'][mask],1e-10)*units.dimensionless)
starts={}
for kind,depth in [('MLCAPE',p[mask][0]-(ps-100)),('MUCAPE',p[mask][0]-(ps-300))]:
    d=depth*units.hPa
    if kind=='MLCAPE': sp,st,sd=mixed_parcel(pp,tt,Td,depth=d)
    else:
        _,_,_,i=most_unstable_parcel(pp,tt,Td,depth=d); sp,st,sd=pp[i],tt[i],Td[i]
    starts[kind]={'p_hpa':float(sp.to('hPa').m),'T_K':float(st.to('K').m),'Td_K':float(sd.to('K').m), 'LCL_hpa':float(lcl(sp,st,sd)[0].to('hPa').m),'top_hpa':float(p[mask][-1])}
events=[]
try: ans=m.profile(p,z,col['TT'],col['SPECHUMD'],col['UU'],col['VV'],soil,events,surface_wind=(fields['UU',200100][0],fields['VV',200100][0]))
except (ValueError,IndexError,ArithmeticError) as exc: ans={'error':str(exc)}
out['flat13024']={'soil_m':float(soil),'ps_hpa':ps,'starts':starts,'events':events,'result':ans}
print('FLAT13024',json.dumps(out['flat13024'],ensure_ascii=False),flush=True)
for cycle in ('2024061218','2024061318','2024061418'):
    stamp=f'{cycle[:4]}-{cycle[4:6]}-{cycle[6:8]}_{cycle[8:]}'
    ai=R/f'drivers_N1_v1/AI/{cycle}/FILE:{stamp}'
    gf=R/f'drivers_N1_v1/GFS/{cycle}/FILE:{stamp}'
    cfg=json.loads(config.read_text())['events']['N1']; idx=m.mask_points(ai,float(cfg['lat']),float(cfg['lon']))
    vals=[]; raws=[]
    for path in (ai,gf):
        all_fields,_=m.records(path); m.field_qc(all_fields,idx)
        slabs,_=m.records(path,idx)
        data={f:np.stack([slabs[f,100*lev] for lev in m.LEVELS]) for f in m.FIELDS}
        rawhash=hashlib.sha256(b''.join(data[f].tobytes() for f in m.FIELDS)+b''.join(slabs[f,200100].tobytes() for f in ('SOILHGT','UU','VV'))).hexdigest()
        raws.append(rawhash)
        answers=[]; total={'LCL 超顶记 0':0,'其他越界/插值告警删失':0,'删失（坏剖面）':0,'饱和气块删失':0}
        for j in range(len(idx)):
            events=[]
            try:
                answer=m.profile(p,*(data[f][:,j] for f in ('GHT','TT','SPECHUMD','UU','VV')),float(slabs['SOILHGT',200100][j]),events,surface_wind=(slabs['UU',200100][j],slabs['VV',200100][j]))
                answers.append((int(idx[j]),answer))
                total['LCL 超顶记 0']+=sum(e['type']=='LCL 超顶记 0' for e in events)
            except (ValueError,IndexError,ArithmeticError) as e:
                answers.append((int(idx[j]),{'error':str(e)}))
                total['删失（坏剖面）']+=1
                total['其他越界/插值告警删失']+=int('warning' in str(e).lower())
                if 'warning' in str(e).lower() and 'Td_K' in str(e):
                    import ast
                    try:
                        parcel=ast.literal_eval(str(e).split('; ',1)[1]); total['饱和气块删失']+=int(parcel['Td_K']>=parcel['T_K'])
                    except (ValueError,IndexError,SyntaxError,KeyError): pass
        vals.append({'sha256':m.sha(path),'field_bytes_sha256':rawhash,'columns':answers,'counts':total})
        print('T0',cycle,path.name,rawhash,total,flush=True)
    mismatch=[]
    for (i,a),(j,b) in zip(vals[0]['columns'],vals[1]['columns']):
        if i!=j or a.keys()!=b.keys() or any((np.float64(a[k]).tobytes()!=np.float64(b[k]).tobytes()) if k!='error' else a[k]!=b[k] for k in a): mismatch.append(i)
    percentiles=[]
    for v in vals:
        good=[x for _,x in v['columns'] if 'error' not in x]
        percentiles.append({k:float(np.percentile([x[k] for x in good],99)) for k in good[0]})
    entry={'cycle':cycle,'AI_sha256':vals[0]['sha256'],'GFS_sha256':vals[1]['sha256'],'field_bytes_sha256':[v['field_bytes_sha256'] for v in vals], 'grid_count':len(idx),'mismatch_count':len(mismatch),'first_mismatch':mismatch[:10],'counts':[v['counts'] for v in vals], 'X99':[percentiles[0],percentiles[1]],'X99_float_bytes_equal':all(np.float64(percentiles[0][k]).tobytes()==np.float64(percentiles[1][k]).tobytes() for k in percentiles[0])}
    out['t0'].append(entry)
    print('T0_COMPARE',json.dumps(entry,ensure_ascii=False),flush=True)
out['saturated_per_file']=[{'cycle':v['cycle'],'source':arm,'count':v['counts'][i]['饱和气块删失'],'grid_count':v['grid_count'],'fraction':v['counts'][i]['饱和气块删失']/v['grid_count']} for v in out['t0'] for i,arm in enumerate(('AI','GFS'))]
output=E/'VALIDITY_GATE_v1e_raw_20261128.json'
assert not output.exists(),output
output.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False))
print('RAW',output,m.sha(output),flush=True)
