"""S0 event-only provisional count, NOT a frozen sample list."""
import csv,datetime as dt,json,pathlib,collections
R=pathlib.Path('/content/r3_s0');a=[json.loads(l) for l in (R/'s0_radar_checked.jsonl').open()]
seen=set()
for name in ('events_verified.csv','r2/events_r2_verified.csv','r2/controls_r2_candidates.csv'):
 for r in csv.DictReader((R/name).open()):
  day=(r.get('peak_utc') or r.get('utc'))[:10];seen.add((r['station'],day))
# Fit event ID from frozen old results, plus candidate and fit initialization date +/-1 day to avoid accidental re-entry.
fit=json.loads((R/'r2/gust_fit_2022.json').read_text())['cases'];fitids={r['id'] for r in fit}
counts=collections.Counter();unique={}; dates=collections.defaultdict(list)
for r in a:
 if not r['radar_40']:continue
 day=r['hit']['utc'][:10]
 if (r['station'],day) in seen or (r['station'],r['ncei_utc'][:10]) in seen or r['id'] in fitids:counts['seen']+=1;continue
 key=(r['station'],day)
 if key not in unique or float(r['hit']['kt'])>float(unique[key]['hit']['kt']):unique[key]=r
for r in unique.values():dates[(r['group'],r['hit']['utc'][:10])].append(r)
selected=[]
for k,g in sorted(dates.items()):
 g.sort(key=lambda r:(-float(r['hit']['kt']),r['hit']['utc'],r['id']))
 selected.extend(g[:3]); counts[k[0]+'_post_cap']+=len(g[:3]);counts['day_cap_removed']+=max(0,len(g)-3)
print('PROVISIONAL',dict(counts),'unique',len(unique),'selected',len(selected),flush=True)
p=R/'s0_events_provisional.json';assert not p.exists();p.write_text(json.dumps(selected,indent=2));print('PROVISIONAL_WRITTEN',p,flush=True)
