"""ACE2-ERA5 versus 6-hourly WB2 ERA5; six inland-ish points.
No raw gridded fields are exported from the Colab runtime.
"""
import numpy as np,xarray as xr,pandas as pd,json,scipy.stats as st,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
P=Path('/content/ace2_analysis_v2');P.mkdir(exist_ok=False)
M=Path('/content/ace2_runs/historical_1979_2008')
assert json.loads((M/'exit.json').read_text())['returncode']==0
meta=json.loads(Path('/content/era5_point_series/points.json').read_text())
# Drop two points on/near Great Lakes: Chicago (Lake Michigan), Buffalo (Lake Ontario).
keep=[k for k,x in enumerate(meta) if x['station'] not in ('KORD','KBUF')]
assert len(keep)==6
model=xr.open_dataset(M/'autoregressive_predictions.nc')
assert model.sizes['time']==43832,(model.sizes,model.valid_time.values[:,-1])
sel={'lat':xr.DataArray([meta[k]['i'] for k in keep],dims='station'),'lon':xr.DataArray([meta[k]['j'] for k in keep],dims='station')}
mt=model.valid_time.values[0]
valid=mt < np.datetime64('2009-01-01T00:00:00')
assert valid.sum()==43831 and not valid[-1]
u=model.UGRD10m.isel(sample=0,**sel).transpose('time','station').values[valid]
v=model.VGRD10m.isel(sample=0,**sel).transpose('time','station').values[valid]
mt=mt[valid]
assert u.shape==(43831,6) and np.isfinite(u).all() and np.isfinite(v).all()
ace=np.hypot(u,v)
ref_t=[];ref_u=[];ref_v=[]
for yr in range(1979,2009):
 f=Path(f'/content/era5_point_series/era5_{yr}.npz');assert f.exists(),f
 z=np.load(f); ref_t.append(z['time']);ref_u.append(z['u'][:,keep]);ref_v.append(z['v'][:,keep])
rt=np.concatenate(ref_t);ru=np.concatenate(ref_u);rv=np.concatenate(ref_v)
# ACE2 starts at 1979-01-01 06:00 (the initialization itself is not a prediction).
ix=np.searchsorted(rt,mt)
assert len(np.unique(ix))==len(mt) and np.array_equal(rt[ix],mt),(rt.shape,mt.shape)
ref=np.hypot(ru[ix],rv[ix]);assert ref.shape==ace.shape and np.isfinite(ref).all()
rows=[];years=mt.astype('datetime64[Y]').astype(int)+1970
assert sorted(set(years))==list(range(1979,2009))
for j,k in enumerate(keep):
 a=ace[:,j];b=ref[:,j]
 am=np.array([a[years==yr].max() for yr in range(1979,2009)])
 bm=np.array([b[years==yr].max() for yr in range(1979,2009)])
 def stats(x):
  loc,scale=st.gumbel_r.fit(x)
  return np.median(x),np.quantile(x,.9),st.gumbel_r.ppf(.98,loc=loc,scale=scale),x.mean()
 sa=stats(am);sb=stats(bm)
 row={'station_anchor':meta[k]['station'],'grid_lat':meta[k]['grid_lat'],'grid_lon':meta[k]['grid_lon'],'n_years':30,'ace_mean_speed':a.mean(),'era_mean_speed':b.mean(),'mean_speed_bias_pct':100*(a.mean()/b.mean()-1)}
 for name,aa,bb in zip(['annual_max_median','annual_max_p90','gumbel_50yr','annual_max_mean'],sa,sb):
  row[f'ace_{name}']=aa;row[f'era_{name}']=bb;row[f'{name}_bias_pct']=100*(aa/bb-1)
 rows.append(row)
 np.savez_compressed(P/f'points_{meta[k]["station"]}.npz',time=mt,ace=a.astype('f4'),era=b.astype('f4'),annual_max_ace=am.astype('f4'),annual_max_era=bm.astype('f4'))
df=pd.DataFrame(rows);df.to_csv(P/'metrics.csv',index=False,float_format='%.5f')
(P/'metrics.json').write_text(df.to_json(orient='records',indent=2))
plt.rcParams.update({'font.size':10})
fig,axs=plt.subplots(1,3,figsize=(17,5),sharey=False)
for ax,key,title in zip(axs,['annual_max_median','annual_max_p90','gumbel_50yr'],['Annual maxima: median','Annual maxima: p90','Gumbel 50-year return level']):
 x=np.arange(len(df));ax.plot(x,df[f'era_{key}'],'o-',label='ERA5 (WB2 1.5° → ACE2 grid)');ax.plot(x,df[f'ace_{key}'],'s-',label='ACE2-ERA5');ax.set_xticks(x,df.station_anchor,rotation=40);ax.set_title(title);ax.set_ylabel('10 m wind speed (m/s)');ax.grid(alpha=.25)
 for j,r in df.iterrows():ax.annotate(f'{r[key+"_bias_pct"]:+.0f}%',(j,r[f'ace_{key}']),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
axs[0].legend(loc='lower left',fontsize=8)
fig.suptitle('6-hourly 10-m wind, 1979–2008 (30 years; 6 selected grid cells)')
fig.text(.01,.01,'Source: ACE2-ERA5 (Ai2 HF, historical SST/ice/CO₂) vs ERA5 (Google WeatherBench2 1959–2022, conservative 1.5°, bilinear to ACE2). Exploratory; not station gusts.',fontsize=8)
fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(P/'annual_max_comparison.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(2,3,figsize=(14,8),sharex=True,sharey=True)
for ax,(j,r) in zip(axs.ravel(),df.iterrows()):
 a=np.load(P/f'points_{r.station_anchor}.npz');bins=np.arange(0,36,.5)
 ax.hist(a['era'],bins=bins,density=True,histtype='step',linewidth=1.6,label='ERA5');ax.hist(a['ace'],bins=bins,density=True,histtype='step',linewidth=1.6,label='ACE2');ax.set_title(f'{r.station_anchor} (ACE2 vs ERA5 mean {r.mean_speed_bias_pct:+.1f}%)');ax.grid(alpha=.2)
axs[0,0].legend();fig.supxlabel('6-hourly 10-m speed (m/s)',y=.065);fig.supylabel('Probability density');fig.suptitle('Mean/whole wind speed distribution: ACE2 vs ERA5 (1979–2008)')
fig.text(.01,.008,'Source: ACE2-ERA5 (Ai2 HF) and ERA5 (Google WeatherBench2 1.5°); 6h vector magnitude; reference conservative+bilinear regridded.',fontsize=8)
fig.tight_layout(rect=[.03,.13,1,.96]);fig.savefig(P/'speed_distribution.png',dpi=160);plt.close(fig)
print(df[['station_anchor','annual_max_median_bias_pct','annual_max_p90_bias_pct','gumbel_50yr_bias_pct','mean_speed_bias_pct']].to_string(index=False),flush=True)
print('ANALYSIS_DONE',len(df),len(mt),flush=True)
