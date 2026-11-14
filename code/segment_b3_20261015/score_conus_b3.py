"""Score strictly complete 10-seed groups and two native/converted HRRR baselines."""
import argparse,csv,json,statistics,collections,pathlib,datetime as dt
p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--source',required=True);p.add_argument('--factor',type=float,default=1.6677111736957388);a=p.parse_args()
R=pathlib.Path(a.out);R.mkdir(exist_ok=True)
rows=[json.loads(s) for s in pathlib.Path(a.checkpoint).read_text().splitlines()]; manifest=list(csv.DictReader(open(a.manifest)));allowed={x['id']:x for x in manifest}
idx=collections.defaultdict(list)
for r in rows:
 if r.get('status')=='ok' and r['id'] in allowed:idx[(r['id'],r['lead_h'])].append(r)
out=[];errors=[]
for e in manifest:
 for lead in (1,2,3):
  group=idx[e['id'],lead];ai=[x for x in group if x['source']==a.source];h=[x for x in group if x['source']=='hrrr']
  if len(ai)!=10 or {x['seed'] for x in ai}!=set(range(101,111)) or len(h)!=1:
   errors.append(dict(id=e['id'],lead=lead,members=len(ai),hrrr=len(h)));continue
  rec=dict(id=e['id'],group=e['group'],station=e['station'],peak_utc=e['utc'],lead_h=lead,model=a.source,obs_kt=float(e['obs_kt']),obs_ms=round(float(e['obs_kt'])*.514444,3),gust_factor=a.factor)
  for win,radius in (('wide',25),('narrow',10)):
   if not all(x.get(win) for x in ai) or not h[0].get(win) or not h[0][win].get('gust') or not h[0][win].get('speed10'):
    errors.append(dict(id=e['id'],lead=lead,window=win,issue='window_missing'));break
   av=[x[win]['ms']*a.factor for x in ai];g=h[0][win]['gust'];v=h[0][win]['speed10'];prefix=win+'_'
   rec[prefix+'ai_median_ms']=statistics.median(av);rec[prefix+'ai_max_ms']=max(av);rec[prefix+'ai_p257']=sum(z>=25.7 for z in av)/10
   rec[prefix+'ai_hit']=int(rec[prefix+'ai_p257']>=.3);rec[prefix+'hrrr_gust_ms']=g['ms'];rec[prefix+'hrrr_hit']=int(g['ms']>=25.7)
   rec[prefix+'hrrr10_ms']=v['ms'];rec[prefix+'hrrr10_xcoef_ms']=v['ms']*a.factor;rec[prefix+'hrrr10_xcoef_hit']=int(v['ms']*a.factor>=25.7)
   rec[prefix+'ai_distance_km_median']=statistics.median(x[win]['distance_km'] for x in ai)
   rec[prefix+'ai_time_bias_min_median']=statistics.median(x[win].get('time_bias_min',(dt.datetime.fromisoformat(x[win]['valid'])-dt.datetime.fromisoformat(e['utc'])).total_seconds()/60) for x in ai)
   rec[prefix+'hrrr_gust_distance_km']=g['distance_km'];rec[prefix+'hrrr_gust_time_bias_min']=(dt.datetime.fromisoformat(g['valid'])-dt.datetime.fromisoformat(e['utc'])).total_seconds()/60
   rec[prefix+'ai_edge_fraction']=sum(x[win]['distance_km']>=radius*.9 for x in ai)/10
   rec[prefix+'hrrr_gust_edge']=int(g['distance_km']>=radius*.9);rec[prefix+'hrrr10_edge']=int(v['distance_km']>=radius*.9)
   if e['group']!='control':
    rec[prefix+'ai_obs_ratio']=rec[prefix+'ai_median_ms']/rec['obs_ms'];rec[prefix+'hrrr_gust_obs_ratio']=g['ms']/rec['obs_ms'];rec[prefix+'hrrr10_xcoef_obs_ratio']=v['ms']*a.factor/rec['obs_ms']
  else:out.append(rec)
assert len(out)+len({(x['id'],x['lead']) for x in errors})==len(manifest)*3
with (R/'scores.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary={}
for lead in (1,2,3):
 e=[x for x in out if x['lead_h']==lead and x['group']!='control'];c=[x for x in out if x['lead_h']==lead and x['group']=='control'];s=dict(events=len(e),controls=len(c),event_median_ai_obs=statistics.median(x['wide_ai_obs_ratio'] for x in e),event_median_hrrr_gust_obs=statistics.median(x['wide_hrrr_gust_obs_ratio'] for x in e),event_median_hrrr10_xcoef_obs=statistics.median(x['wide_hrrr10_xcoef_obs_ratio'] for x in e),ai_hit=sum(x['wide_ai_hit'] for x in e),hrrr_hit=sum(x['wide_hrrr_hit'] for x in e),ai_false=sum(x['wide_ai_hit'] for x in c),hrrr_false=sum(x['wide_hrrr_hit'] for x in c),edge_ai_members=sum(x['wide_ai_edge_fraction']*10 for x in out if x['lead_h']==lead),edge_hrrr_gust=sum(x['wide_hrrr_gust_edge'] for x in out if x['lead_h']==lead),edge_hrrr10=sum(x['wide_hrrr10_edge'] for x in out if x['lead_h']==lead))
 target_events,target_controls=(20,10) if a.source=='v1' else (12,6)
 s['criterion1']=(s['event_median_ai_obs']>=.9*s['event_median_hrrr_gust_obs']) if len(e)>=target_events else None
 # Criterion 2 requires matched full target population; partial groups never interpreted as failure.
 s['criterion2']=((s['ai_hit']>=s['hrrr_hit']) and (s['ai_false']/len(c)<=1.5*s['hrrr_false']/len(c))) if len(e)>=target_events and len(c)>=target_controls else None
 summary[lead]=s
with (R/'summary.json').open('x') as f:json.dump(dict(model=a.source,checkpoint=a.checkpoint,missing_groups=errors,leads=summary),f,indent=2)
print(json.dumps(dict(rows=len(out),errors=errors,summary=summary),indent=2))
