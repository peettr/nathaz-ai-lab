#!/usr/bin/env python3
"""v3 analysis, frozen v2 gates and exact station/day bootstrap method."""
import collections,csv,json,math,random
from pathlib import Path
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent
base=pd.read_csv(R/'paired_inputs_v3.csv',float_precision='round_trip');assert len(base)==4295
out=pd.read_csv(R/'primary_wn.csv');assert len(out)==4295 and not out.duplicated(['station','valid_utc']).any()
assert not base.duplicated(['station','valid_utc']).any()
assert len(pd.read_csv(R/'primary_failures.jsonl',header=None))==0 if (R/'primary_failures.jsonl').stat().st_size else True
v=base.merge(out,on=['station','valid_utc'],suffixes=('_v2',''),validate='one_to_one')
assert len(v)==4295
v['wn_mos_ms']=np.nan
coeff=[]
for (sid,sec),g in v[v.period=='train'].groupby(['station','wn_sector']):
 x=g.wn_ms.to_numpy();y=g.obs_ms.to_numpy();mask=np.isfinite(x)&np.isfinite(y)
 if mask.sum()<2:continue
 a,b=np.linalg.lstsq(np.column_stack((x[mask],np.ones(mask.sum()))),y[mask],rcond=None)[0]
 coeff.append(dict(station=sid,sector=int(sec),slope=float(a),intercept=float(b),n=int(mask.sum())))
 lookup={(c['station'],c['sector']):c for c in coeff}
v['wn_mos_ms']=[max(0,c['slope']*w+c['intercept']) if (c:=lookup.get((s,int(q)))) else np.nan for s,q,w in zip(v.station,v.wn_sector,v.wn_ms)]
# Exact invariance to v2 baseline source (including no value rounding).
for key in ['obs_ms','p90','p99','bilinear_ms','mos_ms']:
 old=key+'_v2' if key+'_v2' in v else key
 assert np.allclose(v[old].to_numpy(),v[key].to_numpy(),rtol=0,atol=0,equal_nan=True),(key,old)
for col in ['bilinear_ms','mos_ms']:
 assert (v[col].to_numpy()==base[col].to_numpy()).all(),col
v.to_csv(R/'paired_main_v3.csv',index=False)
(R/'wn_mos_coefficients_v3.json').write_text(json.dumps(coeff,indent=2))
test=v[v.period=='test']; strong=test[test.obs_ms>=test.p90];assert len(test)==2131 and len(strong)==207
methods={'bilinear':'bilinear_ms','windninja':'wn_ms','mos':'mos_ms','windninja_mos':'wn_mos_ms'}
def mae(g,col):return float(np.nanmean(np.abs(g[col]-g.obs_ms)))
def scored(g):return {m:{'mae_ms':mae(g,c),'bias_ms':float(np.nanmean(g[c]-g.obs_ms)),'n':int(g[c].notna().sum())} for m,c in methods.items()}
a=scored(test);s=scored(strong)
site={k:{'n_all':len(g),'n_strong':len(g[g.obs_ms>=g.p90]),'strong':scored(g[g.obs_ms>=g.p90])} for k,g in test.groupby('station')}
wins=sum(q['strong']['windninja']['mae_ms']<q['strong']['bilinear']['mae_ms'] for q in site.values())
gates=dict(strong_reduction_15pct=(1-s['windninja']['mae_ms']/s['bilinear']['mae_ms']>=.15),station_win_two_thirds=(wins>=8),windninja_mos_increment=(s['windninja_mos']['mae_ms']<s['mos']['mae_ms']),all_time_guardrail=(a['windninja']['mae_ms']<=a['bilinear']['mae_ms']))
# Same Python random.Random, sorted station/day populations, grouping and percentile indexing as bootstrap_v2.py.
rows=list(csv.DictReader((R/'paired_main_v3.csv').open()))
rows=[r for r in rows if r['period']=='test']
f=lambda x:float(x) if x not in ('','nan','NaN') else None
for r in rows:
 for k in ('obs_ms','p90','bilinear_ms','mos_ms','wn_ms','wn_mos_ms'):r[k]=f(r[k])
 r['day']=r['valid_utc'][:10]
strong_rows=[r for r in rows if r['obs_ms']>=r['p90']]
def old_mae(rs,c):
 z=[abs(r[c]-r['obs_ms']) for r in rs if r[c] is not None];return sum(z)/len(z)
def stats(S,A):
 b,w,m,wm=(old_mae(S,c) for c in ('bilinear_ms','wn_ms','mos_ms','wn_mos_ms'))
 return dict(R1=1-w/b,D1=w-b,R3=1-wm/m,D3=wm-m,D4=old_mae(A,'wn_ms')-old_mae(A,'bilinear_ms'))
def group(rs,k):
 g=collections.defaultdict(list)
 for r in rs:g[r[k]].append(r)
 return g
gs_s,gs_a=group(strong_rows,'station'),group(rows,'station')
gd_s,gd_a=group(strong_rows,'day'),group(rows,'day')
stations=sorted(gs_a);days=sorted(gd_a);B=10000
def boot(kind):
 rng=random.Random(20261107);o=collections.defaultdict(list)
 for _ in range(B):
  if kind=='station':
   pick=[rng.choice(stations) for _ in stations];S=[r for k in pick for r in gs_s.get(k,[])];A=[r for k in pick for r in gs_a[k]]
  elif kind=='day':
   pick=[rng.choice(days) for _ in days];S=[r for k in pick for r in gd_s.get(k,[])];A=[r for k in pick for r in gd_a[k]]
  else:
   ps=[rng.choice(stations) for _ in stations];pd_=[rng.choice(days) for _ in days];cnt=collections.Counter(pd_)
   S=[r for k in ps for r in gs_s.get(k,[]) for _ in range(cnt.get(r['day'],0))]
   A=[r for k in ps for r in gs_a[k] for _ in range(cnt.get(r['day'],0))]
  if not S:continue
  for k,val in stats(S,A).items():o[k].append(val)
 return {k:dict(lo=sorted(vals)[int(.025*len(vals))],hi=sorted(vals)[int(.975*len(vals))-1],n=len(vals)) for k,vals in o.items()}
ci={kind:boot(kind) for kind in ('station','day','station_x_day')}
# Height-only replays v2 (metadata unavailable); vegetation-only is primary. Quantify independent 207-row run.
h=pd.read_csv(R/'height_only_strong_wn.csv');assert len(h)==207
hh=strong.merge(h,on=['station','valid_utc'],suffixes=('_primary','_height_only'),validate='one_to_one')
height_mae=float(np.mean(abs(hh.wn_ms_height_only-hh.obs_ms)))
vegetation_mae=s['windninja']['mae_ms']
base_mae=s['bilinear']['mae_ms']
# Large SRTM mismatch sensitivity: original thresholds remain; exclude stations only in post-hoc analysis.
meta=pd.read_csv(R/'stations_v3_inputs.csv');excluded=meta.loc[meta.srtm_minus_station_m.abs()>100,'station'].tolist()
remaining=strong[~strong.station.isin(excluded)]
old=json.loads(Path('./22_Lab/06_Logs/e_terrain/v2_bootstrap/bootstrap_v2_results.json').read_text())
result=dict(status='complete',source='FOUR_v200_GFS',lead_h=24,training_n=2164,test_n=2131,strong_n=207,station_n=12,baseline_identical=True,strong=s,all=a,by_station=site,station_wins=wins,gates=gates,pass_all=all(gates.values()),point=stats(strong_rows,rows),ci95=ci,bootstrap=dict(B=B,seed=20261107,days=len(days)),resolving_power_G1=all(ci[k]['R1']['hi']<.15 for k in ('station','day')),single_factor=dict(height_only=dict(n=207,mae_ms=height_mae,relative_to_v2_wn_ms=height_mae-old['point_mae_strong']['wn_ms']),vegetation_only=dict(n=207,mae_ms=vegetation_mae,relative_to_v2_wn_ms=vegetation_mae-old['point_mae_strong']['wn_ms'])),dem_exclusion=dict(excluded=excluded,remaining_strong_n=len(remaining),wn_mae_ms=mae(remaining,'wn_ms'),bilinear_mae_ms=mae(remaining,'bilinear_ms')),v2_reference=old['point'],wn_mos_missing_test_n=int(test.wn_mos_ms.isna().sum()))
(R/'metrics_v3.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
fmt=lambda x:f'{x:.3f}'
lines=['# R23.2d v3_attrib 拆因复核','',f'主判训练 {2164}、检验 {2131}、强风 {207}；FOUR_v200_GFS +24h，12 站。WindNinja 重跑 {len(v)}/{len(base)}；插值与插值+MOS 逐值相同：是。','',
 '## 三项口径（Source: MeteoSwiss; ESA WorldCover 2021 v200; NASA/USGS SRTM）','',
 'MeteoSwiss ogd-smn_meta_stations.csv 无逐站测风计离地高度字段。station_height_masl 为站海拔，station_height_barometer_masl 为气压计海拔，均不可冒充测风高度；12 站都按任务书缺失回退 10 m。此处无法检验高度修改的因果效应。WorldCover 取像元中心投影到 UTM32N，在 1 km 圆内按 cos(纬度) 面积加权主类；10 km 方形域主类只报不判。DEM 由 v2 同一 SRTM 源/30 m bilinear gdalwarp 重建；站点处双线性采样，主判不做高程订正。','',
 '|站|高度 m/元数据|SRTM−站海拔 m|≤50m|WC 1km|WN 地被|WC 10km|','|---|---:|---:|---|---|---|---|']
for r in meta.itertuples():lines.append(f'|{r.station}|10 / 缺失|{r.srtm_minus_station_m:+.2f}|{str(r.dem_pass_50m)}|{r.worldcover_1km_class}|{r.vegetation}|{r.worldcover_10km_class}|')
lines+=['','## 四项冻结判定与 v2 对照','',
 '|口径|插值|WN v2|WN v3|插值+MOS|WN+MOS v2|WN+MOS v3|','|---|---:|---:|---:|---:|---:|---:|',
 f"|强风 MAE m/s|{fmt(s['bilinear']['mae_ms'])}|{old['point_mae_strong']['wn_ms']:.2f}|{fmt(s['windninja']['mae_ms'])}|{fmt(s['mos']['mae_ms'])}|{old['point_mae_strong']['wn_mos_ms']:.2f}|{fmt(s['windninja_mos']['mae_ms'])}|",
 f"|全时次 MAE m/s|{fmt(a['bilinear']['mae_ms'])}|{old['point_mae_all']['wn_ms']:.2f}|{fmt(a['windninja']['mae_ms'])}|{fmt(a['mos']['mae_ms'])}|—|{fmt(a['windninja_mos']['mae_ms'])}|",'',
 f"G1 强风降幅 {100*result['point']['R1']:.2f}%（v2 {100*old['point']['R1']:.2f}%）：{'通过' if gates['strong_reduction_15pct'] else '不过'}，阈值 ≥15%。",
 f"G2 胜站 {wins}/12（v2 {old['station_wins']}/12）：{'通过' if gates['station_win_two_thirds'] else '不过'}，阈值 ≥8/12。",
 f"G3 WN+MOS MAE {fmt(s['windninja_mos']['mae_ms'])} < 插值+MOS {fmt(s['mos']['mae_ms'])}（v2 {old['point_mae_strong']['wn_mos_ms']:.2f} vs {old['point_mae_strong']['mos_ms']:.2f}）：{'通过' if gates['windninja_mos_increment'] else '不过'}。",
 f"G4 全时次 WN MAE {fmt(a['windninja']['mae_ms'])} ≤ 插值 {fmt(a['bilinear']['mae_ms'])}（v2 {old['point_mae_all']['wn_ms']:.2f} vs {old['point_mae_all']['bilinear_ms']:.2f}）：{'通过' if gates['all_time_guardrail'] else '不过'}。",'',
 '## G1 95% 区间（同 bootstrap_v2.py：B=10000，种子 20261107）','',
 '|口径|v3 点估计|v3 95%|v2 95%|','|---|---:|---:|---:|']
for kind,name in [('station','站点'),('day','日块'),('station_x_day','站×日敏感性')]:
 c=ci[kind]['R1'];prev=old['ci95'][kind]['R1'];lines.append(f"|{name}|{100*result['point']['R1']:.2f}%|[{100*c['lo']:.2f}%, {100*c['hi']:.2f}%]|[{100*prev['lo']:.2f}%, {100*prev['hi']:.2f}%]|")
lines+=['',f"G1 站点及日块区间上限均 <15%：{result['resolving_power_G1']}。",'',
 '## 单因素（只报不判）','',
 f"只换地被、不换高度：检验期强风 {len(strong)} 条 MAE {vegetation_mae:.3f} m/s；由于高度元数据全部缺失，等于主判的对应子集。",
 f"只换高度、不换地被：检验期强风 {len(h)} 条 MAE {height_mae:.3f} m/s；高度全部回退 10 m，配置等于 v2，属原配置重复，不构成高度效应估计。",
 f"DEM |差|>100 m：{excluded}；剔除敏感性强风 {len(remaining)} 条，WN/插值 MAE {mae(remaining,'wn_ms'):.3f}/{mae(remaining,'bilinear_ms'):.3f} m/s。",'',
 '来源： https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_stations.csv；https://esa-worldcover.org/en/data-access；https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/；SRTM https://elevation-tiles-prod.s3.amazonaws.com/skadi/ 。','',
 '资源与会话起止时间另见运行日志/最终回填。']
(R/'results_v3.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:result[k] for k in ['gates','point','station_wins','resolving_power_G1','single_factor']},ensure_ascii=False))
