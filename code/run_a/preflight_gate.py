import csv,collections,json
from datetime import datetime,timedelta
tracks=collections.defaultdict(list)
for x in csv.DictReader(open('/content/a_inputs_v2/tracks.csv')):tracks[x['event']].append(x)
land={x['event']:datetime.fromisoformat(x['landfall_utc']) for x in csv.DictReader(open('/content/a_inputs_v2/landfalls.csv'))}
stations=collections.defaultdict(list)
for x in csv.DictReader(open('/content/a_inputs_v2/stations.csv')):stations[x['event']].append(x)
summary=[];rows=[]
for ev in sorted(land):
 t=land[ev];bad=[];bad_core=[]
 for x in tracks[ev]:
  v=float(x['vmax_kt']);eligible=[]
  for k in (34,50,64):
   if v<=k:continue
   if sum(float(x[f'r{k}_{q}_nmi'])>0 for q in ('ne','se','sw','nw'))>=2:eligible.append(k)
  if len(eligible)<2:
   bad.append({'time_utc':x['time_utc'],'thresholds':eligible})
   if t-timedelta(hours=12)<=datetime.fromisoformat(x['time_utc'])<=t+timedelta(hours=12):bad_core.append(x['time_utc'])
 s=stations[ev]
 summary.append({'event':ev,'metadata_primary':len(s),'metadata_parallel':sum(x['parallel_eligible']=='yes_unverified_height' for x in s),'input_nodes':len(tracks[ev]),'strict_unfittable_nodes':bad,'within_landfall_pm12h_unfittable':bad_core,'model_evaluable':'no' if bad else 'pending_full_run'})
 for x in s:
  rows.append({'event':ev,'station':x['station'],'cohort':'primary;parallel' if x['parallel_eligible']=='yes_unverified_height' else 'primary_only','reason':'BEST_node_missing_two_thresholds;event_unavailable' if bad else 'pending_full_run','pred_10m_sknt':'','observed_10m_sknt':'','error':'','censoring':'not_assessed_no_model_peak','height_unverified':'yes'})
with open('/content/a_preflight_rows.csv','x',newline='') as f:
 w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
open('/content/a_preflight.json','x').write(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)
