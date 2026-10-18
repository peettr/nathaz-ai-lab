#!/usr/bin/env python3
"""A1×C2 development diagnostic. Read-only inputs; no urban verification claim.
Usage: uv run --no-project --with numpy --with matplotlib python run_urban_ratio.py
       --paired PATH --c2 PATH --out DIR
"""
import argparse,csv,gzip,json,math,collections
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt

T=(6,8,10,12); G=(2.5,3.0,3.5); TYPES=('open','wake','rooftop'); HEIGHTS=(50,100)
def number(s):
 try:return float(s)
 except (TypeError,ValueError):return float('nan')
def pct(x):return f'{100*x:.1f}%'
def ci_day(perday,n=1500,seed=20261014):
 # Each calendar day is one block; all stations, forecast cycles and virtual points stay together.
 a=np.array(list(perday.values()),float)
 if len(a)<2:return [float('nan')]*2
 rng=np.random.default_rng(seed);ix=rng.integers(0,len(a),(n,len(a)))
 return np.quantile(a[ix,0].sum(axis=1)/a[ix,1].sum(axis=1),[.025,.975]).tolist()
def frac(v,t):return float(np.mean(v>=t))
def main():
 p=argparse.ArgumentParser();p.add_argument('--paired',required=True);p.add_argument('--c2',required=True);p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 c=list(csv.DictReader(open(a.c2,newline='')))
 ref=np.array([number(r['U_m_s']) for r in c if r['agl_m']=='100' and r['type']=='open'])
 ref_i=np.array([number(r['Iu']) for r in c if r['agl_m']=='100' and r['type']=='open'])
 assert len(c)==741 and len(ref)>0
 ref_u=ref.mean();ref_iu=ref_i.mean();groups={}
 for h in HEIGHTS:
  for typ in TYPES:
   sub=[r for r in c if r['agl_m']==str(h) and r['type']==typ]
   groups[(h,typ)]=(np.array([number(r['U_m_s']) for r in sub]),np.array([number(r['Iu']) for r in sub]))
 # Join FCNv2 raw 100/10 profile to corrected GraphCast 10m, same station/init/lead.
 gr={};fc={};count=collections.Counter()
 with gzip.open(a.paired,'rt',newline='') as f:
  for r in csv.DictReader(f):
   if r['station'] not in ('OKC','PWA') or int(r['lead_h']) not in (24,48):continue
   k=(r['station'],r['init_utc'],r['lead_h'])
   if r['source']=='GRAP_v100_GFS':gr[k]=r
   elif r['source']=='FOUR_v200_GFS':fc[k]=r
 samples={24:[],48:[]};ratios=[]
 for k,r in gr.items():
  f=fc.get(k);count['grap_rows']+=1
  if not f:count['missing_fcn']+=1;continue
  direction=number(r['raw_direction']);sp=number(r['corrected']);f10=number(f['raw_speed']);u100=number(f['fc_u100']);v100=number(f['fc_v100'])
  if not (np.isfinite(direction) and 135<=direction<=225):count['not_south_forecast']+=1;continue
  if not (np.isfinite(sp) and np.isfinite(f10) and f10>=.5 and np.isfinite(u100) and np.isfinite(v100)):
   count['invalid_wind_or_profile']+=1;continue
  ratio=math.hypot(u100,v100)/f10
  if not np.isfinite(ratio):count['invalid_profile']+=1;continue
  date=r['valid_utc'][:10]
  samples[int(k[2])].append((date,k[0],sp,ratio,number(r['metar_speed']),number(r['prob_wind_8']),math.hypot(u100,v100)))
  ratios.append(ratio)
 assert all(len(v)>0 for v in samples.values())
 output={'method':{'sector_forecast_deg':[135,225],'leads_h':[24,48],'baseline':'GraphCast corrected 10m * FCNv2 raw 100m/10m (same station, cycle, lead); C2 normalized to all open100 points mean','peak_g_assumed':3,'g_sensitivity':[2.5,3.5],'days_bootstrap_reps':1500,'thresholds_m_s':T,'c2_points':len(c),'c2_open100_mean_m_s':ref_u,'c2_open100_mean_Iu':ref_iu,'filter_fcn_10m_min_m_s':.5},'counts':dict(count),'samples_by_lead':{str(l):len(x) for l,x in samples.items()},'profile_ratio_quantiles':np.quantile(ratios,[.05,.25,.5,.75,.95]).tolist(),'groups':{},'table':[]}
 for (h,typ),(u,iu) in groups.items():
  q={'n':len(u),'mean_ratio':float(np.mean(u)/ref_u) if len(u) else None,'point_ratio_q10_q50_q90':(np.quantile(u/ref_u,[.1,.5,.9]).tolist() if len(u) else None),'Iu_mean':float(np.mean(iu)) if len(u) else None,'gust_ratios':{str(g):float(np.mean(u*(1+g*iu))/(ref_u*(1+g*ref_iu))) if len(u) else None for g in G}}
  output['groups'][f'{h}_{typ}']=q
  if not len(u):continue
  for lead,ss in samples.items():
   sp=np.array([s[2] for s in ss]);pr=np.array([s[3] for s in ss]);dates=[s[0] for s in ss];u0=sp*pr
   for threshold in T:
    station=frac(sp,threshold);open100=frac(u0,threshold)
    vals=u0[:,None]*(u/ref_u)[None,:];events=vals>=threshold;urban=float(events.mean())
    # Structural source sensitivity, not a confidence interval: direct raw FCNv2 100m
    # instead of a GraphCast-corrected 10m multiplied by FCNv2's vertical ratio.
    direct100=np.array([s[6] for s in ss]);direct_fraction=float(np.mean(direct100[:,None]*(u/ref_u)[None,:]>=threshold))
    point_ranges=np.quantile(events.mean(axis=0),[.1,.5,.9]).tolist()
    daily=collections.defaultdict(lambda:[0,0])
    for d,ev in zip(dates,events):daily[d][0]+=int(ev.sum());daily[d][1]+=len(ev)
    ci=ci_day(daily)
    gust={}
    for g in G:
     gustvals=u0[:,None]*(u*(1+g*iu)/ref_u)[None,:]
     gust[str(g)]=float(np.mean(gustvals>=threshold))
    output['table'].append({'lead_h':lead,'height_agl_m':h,'type':typ,'n_points':len(u),'n_station_cycles':len(ss),'n_distinct_station_days':len(set((s[0],s[1]) for s in ss)),'threshold_m_s':threshold,'station10_fraction':station,'open100_fraction':open100,'city_mean_fraction':urban,'city_mean_day_bootstrap_ci95':ci,'city_point_fraction_q10_q50_q90':point_ranges,'city_mean_direct_fcn100_fraction':direct_fraction,'city_gust_fraction_by_g':gust,'city_mean_minus_open100_pp':100*(urban-open100),'city_mean_minus_station10_pp':100*(urban-station)})
 # Single graphical overview; 24h, threshold8. Display baseline and category range (not an observation CI).
 fig,ax=plt.subplots(figsize=(10,5.5));rows=[r for r in output['table'] if r['lead_h']==24 and r['threshold_m_s']==8]
 for h,mark in ((50,'o'),(100,'s')):
  for i,typ in enumerate(TYPES):
   r=next((r for r in rows if r['height_agl_m']==h and r['type']==typ),None)
   if not r:continue
   pos=i+(0 if h==50 else .25)
   ax.errorbar(pos,100*r['city_mean_fraction'],yerr=[[100*(r['city_mean_fraction']-r['city_mean_day_bootstrap_ci95'][0])],[100*(r['city_mean_day_bootstrap_ci95'][1]-r['city_mean_fraction'])]],fmt=mark,capsize=3,color=('tab:blue' if h==50 else 'tab:orange'),label=f'{h}m AGL' if i==0 else None)
   ax.scatter([pos],[100*r['city_gust_fraction_by_g']['3.0']],marker='x',s=60,color=('tab:blue' if h==50 else 'tab:orange'))
 if rows:
  ax.axhline(100*rows[0]['station10_fraction'],ls=':',color='gray',label='corrected 10m station')
  ax.axhline(100*rows[0]['open100_fraction'],ls='--',color='black',label='estimated open 100m mean')
 ax.set_xticks(np.arange(3)+.125,['open','wake','rooftop']);ax.set_ylabel('Hours exceeding 8 m/s (%)');ax.set_title('24h south-flow scenario | points: mean (95% day CI); crosses: U(1+3 Iu)')
 ax.legend(loc='upper left',bbox_to_anchor=(1.01,1),fontsize=8);ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
 fig.text(.01,.01,'Sources: A1 2023 ASOS-paired GraphCast/FCNv2 forecasts; C2 virtual_summary.csv (development CFD, unvalidated).',fontsize=8)
 fig.tight_layout(rect=[0,.035,.78,1]);fig.savefig(out/'urban_exceedance8.png',dpi=155);plt.close(fig)
 (out/'metrics.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'samples':output['samples_by_lead'],'ref':ref_u,'groups':output['groups'],'plot':str(out/'urban_exceedance8.png')},ensure_ascii=False))
if __name__=='__main__':main()
