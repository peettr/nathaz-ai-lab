import pathlib,csv,datetime as dt,collections,json,hashlib,random,statistics,math
R=pathlib.Path('/content/l2628d1');O=R/'d1';O.mkdir(exist_ok=True)
def number(v):
 try:return float(v) if v.strip() else None
 except (ValueError,AttributeError):return None
tracks=collections.defaultdict(dict)
with (R/'ibtracs.csv').open() as f:
 rd=csv.DictReader(f);next(rd)
 for r in rd:
  if r['SEASON'].strip() not in ('2022','2023','2024'):continue
  n=r['NAME'].strip().upper().replace(' ','-');t=r['ISO_TIME'].strip()[:16]
  tracks[n][dt.datetime.strptime(t,'%Y-%m-%d %H:%M')]=r
rows=[];exclusions=[];manifest=[]
for p in sorted((R/'selected').rglob('*.csv')):
 if '/intensity/data/' not in str(p):continue
 filename=p.name;storm=filename.split('_202')[0].replace('_','-').upper(); issue=dt.datetime.strptime('20'+filename.split('_20')[1][:8],'%Y%m%d%H')
 manifest.append({'file':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 for v in csv.DictReader(p.open()):
  when=dt.datetime.strptime(v['time'],'%Y%m%d%H');best=tracks[storm].get(when)
  if not best:
   exclusions.append({'storm':storm,'issue':issue.isoformat(),'time':when.isoformat(),'reason':'IBTrACS no same-time fix'});continue
  out={'storm':storm,'issue':issue.isoformat(),'time':when.isoformat(),'lead':int((when-issue).total_seconds()/3600)}
  for agency,pres,wind in [('CMA','CMA_PRES','CMA_WIND'),('JTWC','USA_PRES','USA_WIND'),('JMA','TOKYO_PRES','TOKYO_WIND')]:
   out[agency+'_P']=number(best[pres]);w=number(best[wind]);out[agency+'_V']=w*.514444 if w is not None else None
  for m in ('lq','sr'):
   out[m+'_P']=number(v[m+'_min_slp']);out[m+'_V']=number(v[m+'_max_wind_speed'])
  out['obs_P']=number(v['obs_min_slp']);out['obs_V']=number(v['obs_max_wind_speed']);rows.append(out)
assert len(manifest)==50 and len(exclusions)==4 and len(rows)==1810
segments={'12h':lambda x:x==12,'24-72h':lambda x:24<=x<=72,'96-168h':lambda x:96<=x<=168}
def metric(rr,agency,variable,model):
 z=[(r[model+'_'+variable]-r[agency+'_'+variable]) for r in rr if r[agency+'_'+variable] is not None and r[model+'_'+variable] is not None]
 return {'n':len(z),'mae':sum(map(abs,z))/len(z) if z else None,'bias':sum(z)/len(z) if z else None}
def boot(rr,agency,variable,seed):
 paired=[r for r in rr if r[agency+'_'+variable] is not None and r['sr_'+variable] is not None and r['lq_'+variable] is not None]
 storms=sorted(set(r['storm'] for r in paired)); groups={s:[r for r in paired if r['storm']==s] for s in storms};rng=random.Random(seed);draw=[]
 for _ in range(2000):
  sampled=[r for s in rng.choices(storms,k=len(storms)) for r in groups[s]]
  draw.append(metric(sampled,agency,variable,'sr')['mae']-metric(sampled,agency,variable,'lq')['mae'])
 draw.sort();return {'n_storms':len(storms),'difference_sr_minus_pangu':metric(paired,agency,variable,'sr')['mae']-metric(paired,agency,variable,'lq')['mae'],'ci90':[draw[99],draw[1899]],'seed':seed,'draws':2000}
metrics={}
for segment,test in segments.items():
 rr=[r for r in rows if test(r['lead'])];metrics[segment]={'all_rows':len(rr),'storms':len(set(r['storm'] for r in rr)),'agencies':{}}
 for agency in ('CMA','JTWC','JMA'):
  metrics[segment]['agencies'][agency]={}
  for variable in ('P','V'):
   v={model:metric(rr,agency,variable,model) for model in ('lq','sr')}
   v['R']=v['sr']['mae']/v['lq']['mae'] if v['lq']['mae'] else None
   v['bootstrap']=boot(rr,agency,variable,20261118)
   metrics[segment]['agencies'][agency][variable]=v
# peak: unique storm best-track peak among scored times; every issue with any ±12h overlapping points, per-issue model max then median per storm
peaks={}
for storm in sorted(set(r['storm'] for r in rows)):
 rr=[r for r in rows if r['storm']==storm];valid=[r for r in rr if r['CMA_V'] is not None];vpeak=max(r['CMA_V'] for r in valid);ptime=min(dt.datetime.fromisoformat(r['time']) for r in valid if r['CMA_V']==vpeak)
 by=collections.defaultdict(list)
 for r in rr:
  if abs((dt.datetime.fromisoformat(r['time'])-ptime).total_seconds())<=12*3600:by[r['issue']].append(r)
 per=[]
 for issue,v in sorted(by.items()):
  per.append({'issue':issue,'n':len(v),'pangu_error_ms':max(r['lq_V'] for r in v)-vpeak,'sr_error_ms':max(r['sr_V'] for r in v)-vpeak})
 peaks[storm]={'peak_time':ptime.isoformat(),'CMA_peak_ms':vpeak,'n_issues':len(per),'median_pangu_error_ms':statistics.median(x['pangu_error_ms'] for x in per) if per else None,'median_sr_error_ms':statistics.median(x['sr_error_ms'] for x in per) if per else None,'per_issue':per}
def strength(r):
 v=r['CMA_V'];return '<33' if v<33 else '33-50' if v<50 else '>=50'
mechanism={}
for seg,test in [('12h',lambda x:x==12),('24-72h',lambda x:24<=x<=72),('96-168h',lambda x:96<=x<=168)]:
 mechanism[seg]={}
 for band in ('all','<33','33-50','>=50'):
  q=[r for r in rows if test(r['lead']) and r['CMA_V'] is not None and (band=='all' or strength(r)==band)]
  mechanism[seg][band]={'n':len(q),'storms':len(set(r['storm'] for r in q)),'sr_wind_bias_ms':metric(q,'CMA','V','sr')['bias'],'pangu_wind_bias_ms':metric(q,'CMA','V','lq')['bias'],'sr_pressure_bias_hpa':metric(q,'CMA','P','sr')['bias'],'pangu_pressure_bias_hpa':metric(q,'CMA','P','lq')['bias']}
out={'source':{'zenodo_zip_sha256':hashlib.sha256((R/'zenodo.zip').read_bytes()).hexdigest(),'ibtracs_sha256':hashlib.sha256((R/'ibtracs.csv').read_bytes()).hexdigest(),'csv_manifest':manifest},'n_rows':len(rows),'exclusions':exclusions,'metrics':metrics,'peaks':peaks,'mechanism':mechanism,'interpolation':'unavailable: structure/data_day contains radial profile CSV only, no spatial lq fields; cannot derive 2 km interpolated extremum or spatial RMW'}
(O/'metrics.json').write_text(json.dumps(out,indent=2));print('SCORED',len(rows),len(exclusions),json.dumps({s:{a:{v:round(metrics[s]['agencies'][a][v]['R'],3) if metrics[s]['agencies'][a][v]['R'] else None for v in ('P','V')} for a in ('CMA','JTWC')} for s in segments}),flush=True)
