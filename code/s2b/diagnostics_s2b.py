#!/usr/bin/env python3
"""Frozen diagnostic: nearest own-track distance, censored lower bound and figure."""
import csv,json,statistics,math,collections
from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;BASE=HERE.parent.parent
OUT=HERE/'final'
obs=list(csv.DictReader((BASE/'v1/run2/station_rows_v1.csv').open()));sta={(r['event'],r['station']):r for r in obs}
forecast=list(csv.DictReader((OUT/'station_comparison.csv').open()));path=list(csv.DictReader((OUT/'paths.csv').open()))
# station metadata from fixed v1 candidate stations via project code
import sys
sys.path.insert(0,str(BASE/'v1'));import chain_a_v1 as v
old=v.old; events=list(csv.DictReader((BASE/'events_verified.csv').open()));coords={}
for ev in events:
 ss={};land=__import__('datetime').datetime.fromisoformat(ev['landfall_utc'])
 for st in old.CANDIDATES[ev['name']][2].split(','):ss.update(old.stations(st,float(ev['lat']),float(ev['lon']),land))
 coords.update({(ev['name'],s):(x['lat'],x['lon']) for s,x in ss.items()})
# a: BEST b-deck path and RMW, using precisely original v1 source
best=old.parse_hurdat()
for ev in events:
 rmw_series=old.bdeck(ev['atcf_id'].lower())
 for r in best[ev['name']][1]:
  q=old.interp(rmw_series,r['t'],None)
  if not q or not q[0]:continue
  path.append(dict(event=ev['name'],chain='a',lead=0,valid_utc=r['t'].isoformat(),lat=r['lat'],lon=r['lon'],rmw_nmi=q[0]))
# b: s2a paths and contemporaneous same-cycle CARQ RMW from b status
bstatus=json.loads((HERE.parent/'s2a/b_status.json').read_text());bmap={(r['event'],r['nominal_lead_h']):r.get('seed_carq',{}) for r in bstatus}
for r in csv.DictReader((HERE.parent/'s2a/b_paths.csv').open()):
 if int(r['nominal_lead_h']) not in (24,48) or int(r['nominal_lead_h'])==48 and r['event']=='NICHOLAS':continue
 rmw=bmap.get((r['event'],int(r['nominal_lead_h'])),{}).get('rmw')
 path.append(dict(event=r['event'],chain='b',lead=r['nominal_lead_h'],valid_utc=r['valid_utc'],lat=r['lat'],lon=r['lon'],rmw_nmi=rmw))
# a stationary metadata path window ±12h, all chains same event window
from datetime import datetime,timedelta
land={e['name']:datetime.fromisoformat(e['landfall_utc']) for e in events}
groups=collections.defaultdict(list)
for r in path:
 if not r['rmw_nmi'] or not float(r['rmw_nmi']):continue
 t=datetime.fromisoformat(r['valid_utc'])
 if abs((t-land[r['event']]).total_seconds())<=43200:groups[(r['event'],r['chain'],int(r['lead']))].append(r)
drows=[]
for r in obs+forecast:
 chain=r.get('chain','a');lead=int(r.get('nominal_lead_h') or 0)
 if chain=='b_coarse':continue
 key=(r['event'],chain,lead);xy=coords.get((r['event'],r['station']))
 if not xy or not groups[key]:continue
 nearest=min(groups[key],key=lambda p:old.km(*xy,float(p['lat']),float(p['lon'])))
 km=old.km(*xy,float(nearest['lat']),float(nearest['lon']));ratio=km/(float(nearest['rmw_nmi'])*1.852)
 if r['reason']!='eligible':continue
 for field in ('s','g'):
  err=r.get('err_'+field)
  if err in ('',None,'None'):continue
  drows.append(dict(event=r['event'],chain=chain,lead=lead,station=r['station'],variable=field,distance_km=km,rmw_nmi=nearest['rmw_nmi'],distance_rmw=ratio,nearest_utc=nearest['valid_utc'],err=float(err),rmw_bin='<1' if ratio<1 else '1-3' if ratio<=3 else '>3',km_bin='<50' if km<50 else '50-100' if km<=100 else '>100'))
with (OUT/'distance_station_rows.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,drows[0]);w.writeheader();w.writerows(drows)
lines=['# 自身路径最近距离分层（只报告，不进闸）','','来源：NHC BEST (a) / OFCL a-deck (b) / NOAA AIWP 850 hPa 环流追踪 (c)；站点位置来自 IEM ASOS。距离为 ±12 h 内最近点，RMW 为各链该时刻自身冻结值；(a) BEST RMW。误差为模型峰/固定 ASOS 峰−1；站点集仅 v1 eligible。','']
for chain in ('a','b','PANG','FOUR','GRAP'):
 for lead in ([0] if chain=='a' else [24,48] if chain in ('b','PANG') else [48]):
  for field in ('s','g'):
   for dim,bins in [('rmw_bin',['<1','1-3','>3']),('km_bin',['<50','50-100','>100'])]:
    for bi in bins:
     xx=[r['err'] for r in drows if r['chain']==chain and r['lead']==lead and r['variable']==field and r[dim]==bi]
     lines.append(f'{chain} {lead}h {field} {dim} {bi}: n={len(xx)}, med bias={statistics.median(xx):+.3%}, med |e|={statistics.median(map(abs,xx)):.3%}' if xx else f'{chain} {lead}h {field} {dim} {bi}: n=0')
(OUT/'distance_strata.md').write_text('\n'.join(lines)+'\n')
# three-chain censored lower bound, all available 24/48 products
censored=[]
for r in obs:
 if r['reason']!='truncated':continue
 matched=[dict(r,chain='a',nominal_lead_h=0)]+[x for x in forecast if x['event']==r['event'] and x['station']==r['station'] and x['chain'] in ('b','PANG','FOUR','GRAP')]
 for x in matched:
  for field in ('s','g'):
   low=float(r['obs_'+field+'_kt'] or 0);pred=float(x['pred_'+field+'_kt'] or 0)
   censored.append(dict(event=r['event'],chain=x['chain'],lead=x['nominal_lead_h'],station=r['station'],variable=field,lower_bound_kt=low or '',pred_kt=pred or '',below=int(pred<low) if low and pred else '',status='evaluable' if low and pred else 'no_lower_bound_or_prediction'))
with (OUT/'censored_rows.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,censored[0]);w.writeheader();w.writerows(censored)
lines=['# 三链截尾站观测下限检验（不进闸）','','只计 v1 reason=truncated 且记录中有正下限的站；没有完整预测窗口的链不进入该次分母。下限为断报前观测最大值，不代表真实峰。','']
for chain in ('a','b','PANG','FOUR','GRAP'):
 for lead in ([0] if chain=='a' else [24,48] if chain in ('b','PANG') else [48]):
  for field in ('s','g'):
   x=[r for r in censored if r['chain']==chain and int(r['lead'])==lead and r['variable']==field and r['status']=='evaluable']
   lines.append(f'{chain} {lead}h {field}: {sum(int(r["below"]) for r in x)}/{len(x)} 模型低于下限' if x else f'{chain} {lead}h {field}: 无可判')
   for event in sorted(set(r['event'] for r in x)):
    y=[r for r in x if r['event']==event];lines.append(f'  {event}: {sum(int(r["below"]) for r in y)}/{len(y)}')
(OUT/'censored_lower_bound.md').write_text('\n'.join(lines)+'\n')
summary=json.loads((OUT/'summary.json').read_text());fig,ax=plt.subplots(figsize=(9,5));models=['b','PANG','FOUR','GRAP']
for i,chain in enumerate(models):
 rr=[r for r in forecast if r['chain']==chain and int(r['nominal_lead_h'])==48 and r['reason']=='eligible' and r['err_s'] not in ('','None')]
 per=collections.defaultdict(list)
 for r in rr:per[r['event']].append(abs(float(r['err_s'])))
 ax.scatter([i]*len(per),[statistics.median(x)*100 for x in per.values()],label=chain if per else '',alpha=.7)
ax.set_xticks(range(len(models)),models);ax.set_ylabel('Per-event median absolute sustained-wind error (%)');ax.grid(axis='y',alpha=.25)
fig.text(.01,.01,'Sources: NOAA NHC ATCF OFCL / NOAA AIWP Pangu, FOUR, GRAP; IEM ASOS fixed eligible stations. s2b 48h.',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(OUT/'s2b_event_errors.png',dpi=130)
