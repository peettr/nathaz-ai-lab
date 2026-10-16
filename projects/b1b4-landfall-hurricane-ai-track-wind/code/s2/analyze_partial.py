#!/usr/bin/env python3
"""Summarise frozen s2 and separately labeled protocol-corrected s2a."""
import csv,json,statistics,collections
from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
v1=list(csv.DictReader((HERE.parent/'v1/run2/station_rows_v1.csv').open()))
statuses=json.loads((HERE/'s2a/b_status.json').read_text())
full={(x['event'],x['nominal_lead_h']) for x in statuses if x.get('nodes')==97 and not x.get('error')}
b=list(csv.DictReader((HERE/'s2a/b_station_rows.csv').open()))
obs={(r['event'],r['station']):r for r in v1}
comparison=[]
for lead in (24,48,72):
 for event in sorted(set(r['event'] for r in v1)):
  if (event,lead) not in full:continue
  rows=[x for x in b if int(x['nominal_lead_h'])==lead and x['event']==event and x['reason']=='eligible']
  if not rows:continue
  for field in ('s','g'):
   e=[float(x['err_'+field]) for x in rows if x['err_'+field] not in ('','None')]
   comparison.append(dict(chain='b_s2a',event=event,nominal_lead_h=lead,variable=field,n_stations=len(e),median_abs_error=statistics.median(map(abs,e)) if e else '',median_bias=statistics.median(e) if e else '',status='protocol_correction_exploratory'))
with (HERE/'event_comparison_partial.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,comparison[0].keys());w.writeheader();w.writerows(comparison)
results={}
for lead in (24,48,72):
 for field in ('s','g'):
  x=[float(r['err_'+field]) for r in b if (r['event'],lead) in full and int(r['nominal_lead_h'])==lead and r['reason']=='eligible' and r['err_'+field] not in ('','None')]
  results[f'{lead}_{field}']=dict(n=len(x),median_abs_error=statistics.median(map(abs,x)) if x else None,median_bias=statistics.median(x) if x else None)
results['full_events_by_lead']={lead:sorted(e for e,h in full if h==lead) for lead in (24,48,72)}
results['original_prereg_n_full_by_lead']={lead:sum(r.get('nodes')==97 and r['nominal_lead_h']==lead for r in json.loads((HERE/'b_status.json').read_text())) for lead in (24,48,72)}
(HERE/'summary_partial.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
# Censored lower-bound diagnostic: 34 truncated; zero-observation remains unassessable.
records=[]
for r in v1:
 if r['reason']!='truncated':continue
 key=(r['event'],r['station'])
 for field in ('s','g'):
  lower=float(r['obs_'+field+'_kt'] or 0)
  records.append(dict(chain='a',event=r['event'],nominal_lead_h=0,station=r['station'],variable=field,observed_lower_bound_kt=lower or '',predicted_peak_kt=r['pred_'+field+'_kt'],below_lower_bound=(float(r['pred_'+field+'_kt'])<lower if lower else ''),status='evaluable' if lower else 'no_observed_lower_bound'))
  for lead in (24,48,72):
   bs=next((x for x in b if x['event']==r['event'] and x['station']==r['station'] and int(x['nominal_lead_h'])==lead and (r['event'],lead) in full),None)
   records.append(dict(chain='b_s2a',event=r['event'],nominal_lead_h=lead,station=r['station'],variable=field,observed_lower_bound_kt=lower or '',predicted_peak_kt=bs['pred_'+field+'_kt'] if bs else '',below_lower_bound=(float(bs['pred_'+field+'_kt'])<lower if bs and lower else ''),status='evaluable' if bs and lower else 'no_observed_lower_bound' if bs else 'no_full_forecast'))
with (HERE/'censored_lower_bound_partial.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,records[0].keys());w.writeheader();w.writerows(records)
lines=['# 截尾站下限检验（阶段性；c 尚未有路径）','','下限为 v1 所获观测窗口内最大值，非真实峰；0 观测记录不可判。b 使用 s2a 12h 插值修正的探索性结果，仅完整 97 个节点窗口参与。c 未得，禁止把空列算作 0。','']
for chain,lead in [('a',0),('b_s2a',24),('b_s2a',48),('b_s2a',72)]:
 for field in ('s','g'):
  rr=[x for x in records if x['chain']==chain and x['nominal_lead_h']==lead and x['variable']==field]
  good=[x for x in rr if x['status']=='evaluable'];below=[x for x in good if x['below_lower_bound']]
  lines.append(f'{chain} {lead}h {field}: 可判 {len(good)}，模型低于下限 {len(below)}（{len(below)/len(good):.1%}）' if good else f'{chain} {lead}h {field}: 无可判记录')
  for event in sorted(set(x['event'] for x in rr)):
   ee=[x for x in good if x['event']==event]
   if ee:lines.append(f'  {event}: {sum(bool(x["below_lower_bound"]) for x in ee)}/{len(ee)}')
lines.append('\nc: 尚未取得。逐站数据见 censored_lower_bound_partial.csv。')
(HERE/'censored_lower_bound.md').write_text('\n'.join(lines)+'\n')
# Figure: b path errors only. Explicit provenance on figure.
fig,ax=plt.subplots(figsize=(9,4.5))
for lead,mark in ((24,'o'),(48,'s'),(72,'^')):
 xy=[(x['event'],x['landfall_error_km']) for x in statuses if x['nominal_lead_h']==lead and (x['event'],lead) in full and x['landfall_error_km'] is not None]
 ax.scatter([x[0] for x in xy],[x[1] for x in xy],label=f'OFCL {lead}h',marker=mark)
ax.set_ylabel('Landfall-time center error (km)');ax.tick_params(axis='x',labelrotation=50);ax.legend();ax.grid(alpha=.25)
fig.text(.01,.01,'Source: NOAA NHC ATCF a-deck OFCL and HURDAT2 BEST; protocol-corrected s2a (exploratory)',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(HERE/'b_path_errors_s2a.png',dpi=140)
print(json.dumps(results,ensure_ascii=False))
