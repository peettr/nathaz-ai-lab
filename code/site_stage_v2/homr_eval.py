"""Evaluate HOMR instrument and elevation gates only on Colab."""
import csv,json,datetime as dt
from pathlib import Path
P=Path('/content/site_stage_v2/homr_screen.csv');rows=list(csv.DictReader(P.open()))
a=dt.date.fromisoformat('2007-10-01');b=dt.date.fromisoformat('2022-04-01')
for r in rows:
 try:
  wind=[x for x in json.loads(r['wind_records']) if x.get('element')=='WIND']
  intervals=[]
  for x in wind:
   l=dt.date.fromisoformat(x['date']['beginDate'][:10]);z=x['date']['endDate'];u=dt.date(9999,12,31) if z=='Present' else dt.date.fromisoformat(z[:10]);intervals.append((l,u,x['equipment']['equipment']))
  boundaries={a,b}
  for l,u,e in intervals:
   if a<l<b:boundaries.add(l)
   if a<u<b:boundaries.add(u)
  ts=sorted(boundaries);conditions=[]
  for x,y in zip(ts,ts[1:]):
   v={e for l,u,e in intervals if l<=x and u>=y}
   conditions.append((x.isoformat(),','.join(sorted(v))))
  r['instrument_ok']=str(all(v=='ANEMSONIC' for x,v in conditions)).lower()
  r['instrument_segments']=json.dumps(conditions)
  r['relocation_ok']=str(len(json.loads(r['relocations_during']))==0).lower()
  r['elevation_ok']=str(float(r['elev_m'])<=1000).lower()
 except Exception as e:r['eval_error']=repr(e)
fields=list(rows[0]);fields+=['instrument_ok','instrument_segments','relocation_ok','elevation_ok','eval_error']
out=P.with_name('homr_gates.csv')
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
for g in ('plains','other'):
 q=[r for r in rows if r['region']==g and r.get('instrument_ok')=='true' and r.get('relocation_ok')=='true' and r.get('elevation_ok')=='true']
 print(g,len(q),[r['station'] for r in q],flush=True)
print('errors',[(r['station'],r.get('eval_error')) for r in rows if r.get('eval_error')],flush=True)
