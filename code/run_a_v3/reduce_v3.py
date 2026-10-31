"""Small audit/report reduction; use only completed Colab outputs; never alter frozen rules."""
import csv,json,statistics,collections,math
from pathlib import Path
from datetime import datetime
P=Path('/content'); tags=('main','hours6','hours18','weight01','weight1','bdeck')
stations=list(csv.DictReader((P/'stations.csv').open())); events=sorted({x['event'] for x in stations})
obs_pool=collections.Counter((r['event'],r['station']) for r in stations)
assert len(events)==15 and all(n==1 for n in obs_pool.values())
results={}; summaries={}; allrows={}
for tag in tags:
    base=P/f'a_v3_r2_{tag}'
    status=(base.with_suffix('.exit')).read_text().strip() if base.with_suffix('.exit').exists() else None
    if status!='0' or not base.with_suffix('.csv').exists():
        summaries[tag]={'exit':status,'reason':base.with_suffix('.log').read_text()[-2000:] if base.with_suffix('.log').exists() else 'missing'}
        continue
    rows=list(csv.DictReader(base.with_suffix('.csv').open()));allrows[tag]=rows
    # Parallel is a subset of primary; use station table to prevent misclassification.
    eligible={(s['event'],s['station']) for s in stations if s['parallel_eligible']=='yes_unverified_height'}
    bypool={p:[r for r in rows if r['error'] and (p=='primary' or (r['event'],r['station']) in eligible)] for p in ('primary','parallel')}
    counts={p:dict(collections.Counter(r['event'] for r in rs)) for p,rs in bypool.items()}
    stats={p:{'n':len(rs),'B':statistics.median(float(r['error']) for r in rs) if rs else None,'M':statistics.median(abs(float(r['error'])) for r in rs) if rs else None,
              'events_ge3':sum(counts[p].get(e,0)>=3 for e in events)} for p,rs in bypool.items()}
    tier={}
    for e in events:
        one=next((r for r in rows if r['event']==e),None)
        tier[e]=dict(collections.Counter(str(f['tier']) for f in json.loads(one['rmw_fits']))) if one else {}
    summaries[tag]={'exit':status,'stats':stats,'counts':counts,'tiers':tier}
(P/'v3_summary.json').write_text(json.dumps(summaries,indent=2))
print(json.dumps({t:{'exit':v.get('exit'),'primary':v.get('stats',{}).get('primary')} for t,v in summaries.items()}))
