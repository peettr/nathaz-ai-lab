import pandas as pd, numpy as np,pathlib
from scipy.signal import find_peaks
r=pathlib.Path('/content/L26_18')
for i in range(2):
 d=pd.read_csv(r/f'sfmr_ian_{i}.csv',skiprows=[1]);d['time']=pd.to_datetime(d.time,utc=True);print('WINDOW',i,len(d),flush=True)
 for f,g in d.groupby('flight_id'):
  g=g.sort_values('time').copy();g.loc[(g.FLAG!=0)|(g.SWS<0)|(g.NGC<4),'SWS']=np.nan
  g['smooth']=g.SWS.rolling(11,center=True,min_periods=6).median()
  series=g.smooth.interpolate(limit=5).fillna(99).to_numpy()
  peaks,props=find_peaks(-series,prominence=15,distance=600)
  print('FLIGHT',f,'candidates',len(peaks),flush=True)
  for p in peaks:
   a=g.iloc[p];print(a.time.strftime('%H:%M:%S'),a.latitude,a.longitude,'min',round(a.smooth,1),'prom',round(props['prominences'][np.where(peaks==p)[0][0]],1),'prevmax',round(np.nanmax(series[max(0,p-1200):p]),1),'nextmax',round(np.nanmax(series[p+1:p+1200]),1),flush=True)
