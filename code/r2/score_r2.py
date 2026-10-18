"""Aggregate fixed-seed r2 rows; never count incomplete sets as failures."""
import csv,json,statistics,collections,pathlib,math
ROOT=pathlib.Path(__file__).parent
factor=json.loads((ROOT/'gust_fit_2022.json').read_text())['factor']
rows=[json.loads(x) for x in (ROOT/'v1_main_complete.jsonl').read_text().splitlines()]
gfs=[json.loads(x) for x in (ROOT/'v1_gfs_complete.jsonl').read_text().splitlines()] if (ROOT/'v1_gfs_complete.jsonl').exists() else []
index=collections.defaultdict(list)
for x in rows+gfs:index[(x['id'],x['lead_h'],x['condition'])].append(x)
out=[]
for (eid,lead,condition),r in sorted(index.items()):
 ai=[x for x in r if x.get('status')=='ok' and x['source']=='v1'] if condition=='ARCO_ERA5' else [x for x in r if x.get('status')=='ok']
 hr=next((x for x in r if x.get('status')=='ok' and x['source']=='hrrr'),None)
 if condition!='ARCO_ERA5':
  hr=next((x for x in index.get((eid,lead,'ARCO_ERA5'),[]) if x.get('status')=='ok' and x['source']=='hrrr'),None)
 if not hr or len(ai)!=10 or {x['seed'] for x in ai}!={*range(101,111)}:continue
 b={'id':eid,'group':ai[0]['group'],'station':ai[0]['station'],'lead_h':lead,'condition':condition,'obs_kt':ai[0]['obs_kt'],'obs_ms':round(ai[0]['obs_kt']*.514444,3),'factor_fit_2022':factor}
 for window in ('wide','narrow'):
  av=[x[window]['ms']*factor for x in ai if x.get(window)]
  if len(av)!=10:break
  gb=hr[window]['gust'];vb=hr[window]['speed10']
  b[f'{window}_ai_median_ms']=statistics.median(av);b[f'{window}_ai_max_ms']=max(av)
  b[f'{window}_ai_p257']=sum(x>=25.7 for x in av)/10
  b[f'{window}_hrrr_gust_ms']=gb['ms'] if gb else None
  b[f'{window}_hrrr_speedxcoef_ms']=vb['ms']*factor if vb else None
  b[f'{window}_edge_ai_fraction']=sum(x[window]['distance_km']>=25*.9 for x in ai)/10 if window=='wide' else None
  b[f'{window}_edge_hrrr_gust']=int(gb['distance_km']>=22.5) if gb and window=='wide' else None
  b[f'{window}_edge_hrrr_speed']=int(vb['distance_km']>=22.5) if vb and window=='wide' else None
  b[f'{window}_ai_hit']=int(b[f'{window}_ai_p257']>=.3)
  b[f'{window}_hrrr_hit']=int(gb['ms']>=25.7) if gb else None
  if b['group']!='control':
   b[f'{window}_ai_obs_ratio']=b[f'{window}_ai_median_ms']/b['obs_ms']
   b[f'{window}_hrrr_obs_ratio']=gb['ms']/b['obs_ms'] if gb else None
 else:out.append(b)
if not out:raise ValueError('No complete 10-member cases')
p=ROOT/'scored_r2.csv'
with p.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary={}
for condition in sorted({x['condition'] for x in out}):
 for lead in (1,2,3):
  a=[x for x in out if x['lead_h']==lead and x['condition']==condition]
  e=[x for x in a if x['group']!='control'];c=[x for x in a if x['group']=='control']
  k=f'{condition}_L{lead}'
  summary[k]={'events':len(e),'controls':len(c),'ratio_ai':statistics.median(x['wide_ai_obs_ratio'] for x in e) if e else None,'ratio_hrrr':statistics.median(x['wide_hrrr_obs_ratio'] for x in e) if e else None,'hit_ai':sum(x['wide_ai_hit'] for x in e),'hit_hrrr':sum(x['wide_hrrr_hit'] for x in e),'false_ai':sum(x['wide_ai_hit'] for x in c),'false_hrrr':sum(x['wide_hrrr_hit'] for x in c)}
(ROOT/'summary_r2.json').write_text(json.dumps(summary,indent=2))
print('ROWS',len(out),'SUMMARY',json.dumps(summary,indent=2))
