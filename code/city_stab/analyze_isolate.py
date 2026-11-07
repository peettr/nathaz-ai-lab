"""Summarize compact Colab Case E isolation traces on 工作站 (no solver)."""
from pathlib import Path
import csv,json,statistics,math
R=Path(__file__).resolve().parent
out={}
for tag in ('r1','r2'):
 rows=list(csv.DictReader((R/f'iso_{tag}_city_stability.csv').open()))
 finite=[r for r in rows if not r['first_nonfinite_xyz_component']]
 def val(r,k):return float(r[k])
 rates=[];balance=[]
 for i in range(5,len(finite)):
  a,b=finite[i-5],finite[i];mass=val(b,'mass_fluid');base=val(a,'mass_fluid')
  rates.append((int(b['step']),(mass/base-1)*100))
 for i in range(1,len(finite)):
  a,b=finite[i-1],finite[i]
  dm=val(b,'mass_fluid')-val(a,'mass_fluid')
  flux=-100*(val(b,'flux_net_out')+val(a,'flux_net_out'))
  balance.append({'step':int(b['step']),'delta_mass':dm,'minus_outflux_trap':flux,'residual':dm-flux})
 out[tag]={'rows':len(rows),'last':int(rows[-1]['step']),'max_speed_finite':max(val(r,'max_u_lattice') for r in finite),
 'rho_finite_after3000':[min(val(r,'min_rho') for r in finite if int(r['step'])>=3000),max(val(r,'max_rho') for r in finite if int(r['step'])>=3000)],
 'rate1000_first_over_0p05':next(((s,v) for s,v in rates if s>=4000 and abs(v)>=.05),None),
 'rate1000_max_abs':max(rates,key=lambda x:abs(x[1])),
 'mass3000_to_last_pct':(val(finite[-1],'mass_fluid')/next(val(r,'mass_fluid') for r in finite if r['step']=='3000')-1)*100,
 'flux_finite_mean':{k:statistics.mean(val(r,k) for r in finite) for k in ('flux_west','flux_east','flux_south','flux_north','flux_top','flux_net_out')},
 'last_finite':{k:finite[-1][k] for k in ('step','mass_fluid','flux_west','flux_east','flux_south','flux_north','flux_top','flux_net_out')},
 'first_bad':rows[-1] if len(finite)<len(rows) else None,
 'balance_median_abs_residual':statistics.median(abs(d['residual']) for d in balance),
 'balance_median_abs_delta_mass':statistics.median(abs(d['delta_mass']) for d in balance)}
 if tag=='r2':
  d=json.loads((R/'iso_r2_offset_samples_a_r10.json').read_text());points=d['rows'];assert len(points)==80
  groups={'all':set(x['id'] for x in points),'wall':{50,51,52,54},'open':{23,25,37,17}}
  metrics={}
  for label,ids in groups.items():
   q=[r for r in points if r['id'] in ids];assert len(q)==len(ids)
   obs=[r['after'] for r in q]
   metrics[label]={}
   for key in ('sim_ratio','exp_ratio'):
    sim=[r['sample']['plus_dx'][key] for r in q]
    metrics[label][key]={'MAE':statistics.mean(abs(x-y) for x,y in zip(sim,obs)),
      'r':statistics.correlation(sim,obs),'mean_ratio':statistics.mean(sim)/statistics.mean(obs)}
  out[tag]['metrics']=metrics
  out[tag]['upstream']={str(p['x_local_m']):p['fraction_input'] for p in d['upstream'] if p['z_m']==2.0 and p['x_local_m'] in (25.0,42.0)}
(R/'iso_summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,indent=2,ensure_ascii=False))
