"""Prepare S0 event census and deterministic year-stratified selection; no AI."""
import csv,datetime as dt,json,random,collections,math,tarfile
R='/content/'
with tarfile.open(R+'s0_prior_inputs.tar.gz') as f:f.extractall('/content/prior',filter='data')
seen=set()
for name in ('events_verified.csv','r2/events_r2_verified.csv','r2/controls_r2_candidates.csv'):
 for r in csv.DictReader(open('/content/prior/'+name)):
  date=(r.get('peak_utc') or r.get('utc') or '')[:10]
  if date:seen.add((r['station'],date))
for x in json.load(open(R+'s0_fit_actual.json')):seen.add((x['station'],x['utc'][:10]))
allrows=[json.loads(l) for name in ('s0_radar_checked.jsonl','s0_radar_extra.jsonl') for l in open(R+name)]
grid={x['id']:x for x in json.load(open(R+'s0_grid_checked.json'))}
# Extra 21 rows can coincide with already screened IDs but were METAR failures, never duplicate selected IDs.
counts=collections.Counter();unique={}
for x in allrows:
 counts['metar_eligible']+=1
 if x['radar_35']:counts['radar_35']+=1
 if not x['radar_40']:
  counts['radar_40_fail']+=1
  if x['radar_35']:counts['radar_35_only']+=1
  continue
 counts['radar_40_pass']+=1
 day=x['hit']['utc'][:10]
 if (x['station'],day) in seen or (x['station'],x['ncei_utc'][:10]) in seen:counts['seen_removed']+=1;continue
 if x['id'] not in grid or not grid[x['id']]['grid_inside']:
  counts['grid_removed']+=1;continue
 x.update({k:grid[x['id']][k] for k in ('grid_y','grid_x','grid_nearest_km','grid_edge_km')})
 key=(x['station'],day)
 if key not in unique or (-float(x['hit']['kt']),x['hit']['utc'],x['id'])<(-float(unique[key]['hit']['kt']),unique[key]['hit']['utc'],unique[key]['id']):unique[key]=x
byday=collections.defaultdict(list)
for x in unique.values():byday[(x['group'],x['hit']['utc'][:10])].append(x)
all_events=[]
for key,rows in sorted(byday.items()):
 rows.sort(key=lambda x:(-float(x['hit']['kt']),x['hit']['utc'],x['id']))
 all_events+=rows[:3];counts['day_capped']+=max(0,len(rows)-3)
selected=[];rng=random.Random(20261016)
for group,target in [('v1',120),('conus',80)]:
 grp=[x for x in all_events if x['group']==group];counts[group+'_eligible']=len(grp)
 if len(grp)<=target:selected+=grp;continue
 strata=collections.defaultdict(list)
 for x in grp:strata[int(x['hit']['utc'][:4])].append(x)
 allocations={y:int(target*len(v)/len(grp)) for y,v in strata.items()}
 remain=target-sum(allocations.values())
 for y in sorted(strata,key=lambda y:(-(target*len(strata[y])/len(grp)-allocations[y]),y))[:remain]:allocations[y]+=1
 for y in sorted(strata):
  rows=sorted(strata[y],key=lambda x:(x['hit']['utc'],x['station'],x['id']))
  selected+=rng.sample(rows,allocations[y])
 counts[group+'_selected']=sum(x['group']==group for x in selected)
selected.sort(key=lambda x:(x['group'],x['hit']['utc'],x['station'],x['id']))
with open(R+'s0_event_census.json','x') as f:json.dump(all_events,f)
with open(R+'s0_event_selected.json','x') as f:json.dump(selected,f)
with open(R+'s0_event_counts.json','x') as f:json.dump(counts,f,indent=2)
print('S0_EVENT_COUNTS',dict(counts),'selected',len(selected),flush=True)
