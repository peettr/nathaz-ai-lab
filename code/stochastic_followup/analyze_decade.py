"""Compare paired SHiELD-emulator annual maxima with ERA5 at eight grid points."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import gumbel_r
import matplotlib.pyplot as plt
base=Path('/content/ace_stochastic_followup')
labels=['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']
for label in ('det','sto'):
    s=json.loads((base/f'{label}_decade'/'exit.json').read_text())
    assert s['returncode']==0,s
out=base/'analysis'
out.mkdir(exist_ok=False)
ds={label:xr.open_dataset(base/f'{label}_decade'/'output'/'autoregressive_predictions.nc') for label in ('det','sto')}
t=ds['det'].valid_time.values[0]
assert np.array_equal(t,ds['sto'].valid_time.values[0])
assert len(t)==14611,(len(t),t[0],t[-1])
assert t[0]==np.datetime64('1979-01-01T06:00:00') and t[-1]==np.datetime64('1988-12-31T18:00:00')
years=t.astype('datetime64[Y]').astype(int)+1970
rows=[]
for name in labels:
    old=np.load('/content/points_'+name+'.npz')
    assert np.array_equal(old['time'][:len(t)],t)
    # These are the ACE2-ERA5 grid coordinates; SHiELD models use same 1-degree grid.
    # Array from prior reference is ERA5 1.5-degree field interpolated to ACE grid.
    stations=json.loads(Path('/content/stochastic_points.json').read_text())
    p=next(x for x in stations if x['station']==name)
    i,j=p['i'],p['j']
    e=old['era'][:len(t)]
    series={'ERA5':e,'ACE2-ERA5':old['ace'][:len(t)]}
    for label,nice in [('det','ACE2-SHiELD'),('sto','ACE2S-SHiELD+')]:
        d=ds[label]
        assert abs(float(d.lat[i])-p['grid_lat'])<0.0001
        assert abs(float(d.lon[j])-p['grid_lon'])<0.0001
        u=d.UGRD10m.isel(sample=0,lat=i,lon=j).values
        v=d.VGRD10m.isel(sample=0,lat=i,lon=j).values
        series[nice]=np.hypot(u,v)
    for key,x in series.items():
        assert len(x)==len(t) and np.isfinite(x).all()
        maxima=np.array([x[years==year].max() for year in range(1979,1989)])
        assert len(maxima)==10
        loc,scale=gumbel_r.fit(maxima)
        rows.append(dict(station=name,model=key,n_steps=len(t),n_years=10,
                         mean_speed=float(x.mean()),max_median=float(np.median(maxima)),
                         max_p90=float(np.quantile(maxima,.9)),gumbel_50yr=float(gumbel_r.ppf(.98,loc=loc,scale=scale)),
                         annual_maxima=';'.join(f'{v:.3f}' for v in maxima)))
        np.savez_compressed(out/f'{name}_{key}.npz',time=t,speed=x.astype('f4'),annual_maxima=maxima.astype('f4'))
df=pd.DataFrame(rows)
ref=df[df.model=='ERA5'].set_index('station')
for col in ('mean_speed','max_median','max_p90','gumbel_50yr'):
    df[col+'_bias_era5_pct']=df.apply(lambda row:100*(row[col]/ref.loc[row.station,col]-1),axis=1)
for col in ('mean_speed','max_median','max_p90','gumbel_50yr'):
    deterministic=df[df.model=='ACE2-SHiELD'].set_index('station')[col]
    df[col+'_bias_det_pct']=df.apply(lambda row:100*(row[col]/deterministic[row.station]-1) if row.model=='ACE2S-SHiELD+' else float('nan'),axis=1)
df.to_csv(out/'comparison_ten_years.csv',index=False,float_format='%.5f')
print(df[['station','model','mean_speed_bias_era5_pct','max_median_bias_era5_pct','max_p90_bias_era5_pct','gumbel_50yr_bias_era5_pct','gumbel_50yr_bias_det_pct']].to_string(index=False),flush=True)
fig,axs=plt.subplots(1,2,figsize=(14,5),layout='constrained')
colors={'ERA5':'black','ACE2-ERA5':'royalblue','ACE2-SHiELD':'tab:orange','ACE2S-SHiELD+':'tab:green'}
xs=np.arange(len(labels))
for key in colors:
    d=df[df.model==key].set_index('station').loc[labels]
    offset=list(colors).index(key)*.18-.27
    axs[0].bar(xs+offset,d.max_median,width=.18,label=key,color=colors[key])
    axs[1].bar(xs+offset,d.mean_speed,width=.18,label=key,color=colors[key])
axs[0].set_title('1979–1988 annual-max median, 6-hourly 10 m wind')
axs[1].set_title('1979–1988 mean of 6-hourly 10 m wind')
for a in axs:
    a.set_xticks(xs,labels);a.set_ylabel('m s$^{-1}$');a.grid(axis='y',alpha=.2)
axs[0].legend(fontsize=8,ncol=2)
fig.text(.02,.005,'Sources: Ai2 ACE2-ERA5 / ACE2-SHiELD / ACE2S-SHiELD+; WeatherBench2 ERA5 1.5° conservative regrid. SHiELD models do not target ERA5.',fontsize=8)
fig.savefig(out/'paired_shield_decade.png',dpi=160)
print('ANALYSIS_DONE',len(df),len(t),flush=True)
