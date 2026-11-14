import pandas as pd,numpy as np,pathlib,json
r=pathlib.Path('/content/L26_18'); records=[]
fixes=[('20220927H1','2022-09-27T10:47:48Z',24.08,-83.75),('20220927I1','2022-09-27T22:01:15Z',24.16,-83.13),('20220928U1','2022-09-28T02:05:29Z',24.64,-83.01)]
t0=np.array([pd.Timestamp(t).timestamp() for _,t,_,_ in fixes]);clat=np.array([x[2] for x in fixes]);clon=np.array([x[3] for x in fixes]);print('FIXES',fixes)
for ii in range(2):
 d=pd.read_csv(r/f'sfmr_ian_{ii}.csv',skiprows=[1]);d['time']=pd.to_datetime(d.time,utc=True)
 for flight,tfix,lat,lon in fixes:
  if flight not in d.flight_id.values or (ii==0 and flight!='20220927H1') or (ii==1 and flight=='20220927H1'):continue
  g=d[d.flight_id==flight].sort_values('time').copy();g.loc[(g.FLAG!=0)|(g.SWS<0)|(g.NGC<4),'SWS']=np.nan
  g['smooth']=g.SWS.rolling(11,center=True,min_periods=8).mean()
  seconds=g.time.astype('int64').to_numpy()/1e9
  lat0=np.interp(seconds,t0,clat);lon0=np.interp(seconds,t0,clon)
  x=np.deg2rad(g.latitude.to_numpy());y=np.deg2rad(lat0);z=np.sin((x-y)/2)**2+np.cos(x)*np.cos(y)*np.sin(np.deg2rad(g.longitude.to_numpy()-lon0)/2)**2
  g['radius']=12742*np.arcsin(np.sqrt(np.clip(z,0,1)))
  crossing=pd.Timestamp(tfix)
  for side in ('in','out'):
   z=g[(g.time>=crossing-pd.Timedelta(minutes=30))&(g.time<=crossing+pd.Timedelta(minutes=30))&(g.time<=crossing if side=='in' else g.time>=crossing)&(g.radius>=5)&(g.radius<=120)&g.smooth.notna()]
   if z.empty:continue
   top=z.loc[z.smooth.idxmax()];print('LEG',flight,side,'n',len(z),'rmax',round(z.radius.max(),2),'peak',top.time,round(top.radius,2),round(top.smooth,2),'near',round(z.radius.min(),2),flush=True)
   records.append({'flight':flight,'leg':side,'crossing_utc':tfix,'center_lat_lon':[lat,lon],'n':len(z),'furthest_km':float(z.radius.max()),'peak_time_utc':top.time.isoformat(),'peak_radius_km':float(top.radius),'peak_wind_ms':float(top.smooth),'nearest_km':float(z.radius.min()),'qualifies':bool(z.radius.max()>=70 and z.radius.min()<=15 and top.radius>=10)})
(r/'sfmr_legs.json').write_text(json.dumps({'center_method':'10 s SFMR wind minimum near eye, flight position, linearly interpolated across H1/I1/U1 centers (no b-deck/ATCF/SAR center)','fixes':fixes,'legs':records},indent=2));print('OBS',records,flush=True)
