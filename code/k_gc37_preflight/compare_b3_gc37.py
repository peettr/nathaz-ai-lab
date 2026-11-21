#!/usr/bin/env python3
"""Frozen B3 paired GFS-zero versus scaled-upper-w forecast diagnostic."""
import argparse,json,math,pathlib,numpy as np
P=(850,700,500,250)
CENTER_LAT,CENTER_LON=40.17563,360-103.22203
p=argparse.ArgumentParser();p.add_argument('--root',default='/content/r234c_gc37_428d60ab');p.add_argument('--cycle',default='2020060806');p.add_argument('--steps',type=int,default=4);p.add_argument('--zero-tag',default='zero');p.add_argument('--scaled-tag',default='scaled');a=p.parse_args()
r=pathlib.Path(a.root);z=np.load(r/f'forecast_{a.cycle}_{a.zero_tag}_{a.steps}step'/f'step_{a.steps:02d}.npz');s=np.load(r/f'forecast_{a.cycle}_{a.scaled_tag}_{a.steps}step'/f'step_{a.steps:02d}.npz')
lat=np.arange(-90.,90.001,.25);lon=np.arange(0.,360.,.25)
la=np.deg2rad(lat[:,None]);lo=np.deg2rad(lon[None,:]);dlat=la-math.radians(CENTER_LAT);dlon=lo-math.radians(CENTER_LON)
h=np.sin(dlat/2)**2+np.cos(la)*math.cos(math.radians(CENTER_LAT))*np.sin(dlon/2)**2
mask=6371*2*np.arcsin(np.sqrt(np.maximum(h,0)))<=1000
if mask.shape!=(721,1440):raise AssertionError(mask.shape)
rows={}
for var in ['temperature','u_component_of_wind','v_component_of_wind']:
 for level in P:
  key=f'{var}_{level}';d=z[key]-s[key]
  rows[key]={'global_rmse':float(np.sqrt(np.mean(d.astype('float64')**2))),'akron_1000km_rmse':float(np.sqrt(np.mean(d[mask].astype('float64')**2))),'akron_1000km_max_abs':float(np.max(np.abs(d[mask])))}
key='mean_sea_level_pressure';d=(z[key]-s[key])/100
rows[key]={'global_rmse_hpa':float(np.sqrt(np.mean(d.astype('float64')**2))),'akron_1000km_rmse_hpa':float(np.sqrt(np.mean(d[mask].astype('float64')**2))),'akron_1000km_max_abs_hpa':float(np.max(np.abs(d[mask])))}
passed=all(rows[f'{v}_{p}']['akron_1000km_rmse']<0.5 for v in ('temperature','u_component_of_wind','v_component_of_wind') for p in (850,700,500))
result={'cycle':a.cycle,'valid_time':'2020-06-09 06Z','steps':a.steps,'akron_1000km_cells':int(mask.sum()),'pass_b3':passed,'thresholds':'strict <0.5 K or <0.5 m/s for 850/700/500 hPa T/U/V (500 hPa and below)','fields':rows}
out=r/'B3_P24_SENSITIVITY.json';out.open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
