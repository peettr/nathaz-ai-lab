#!/usr/bin/env python3
"""Colab-only PALUPD 111m ten-minute observations; month checkpoints.
Source: Morrison et al. ESSD 2025, Zenodo 17710093, L3v1.42.
"""
import io, json, tarfile, time
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
import requests

root=Path('/content/m5/paris_obs');root.mkdir(parents=True,exist_ok=True)
url='https://zenodo.org/api/records/17710093/files/paris_dwl_L3V1.42_{ym}_600s.tar.gz/content'
for period in pd.period_range('2023-06','2024-02',freq='M'):
    ym=str(period).replace('-','_');dest=root/f'palupd_{ym}.csv'
    if dest.exists():
        print('OBS_SKIP',ym,flush=True);continue
    t=time.monotonic();response=requests.get(url.format(ym=ym),timeout=240);response.raise_for_status()
    rows=[]
    with tarfile.open(fileobj=io.BytesIO(response.content),mode='r:gz') as tf:
        for member in tf:
            if not member.isfile() or not member.name.endswith('.nc'):continue
            with h5py.File(io.BytesIO(tf.extractfile(member).read()),'r') as f:
                names=[x.decode() if isinstance(x,bytes) else str(x) for x in f['station'][:]]
                if 'PALUPD' not in names:continue
                s=names.index('PALUPD');alt=f['altitude'][:]
                ground=float(f['station_altitude'][s]-f['station_height'][s]);k=int(np.abs(alt-ground-111).argmin())
                z=float(alt[k]-ground)
                if abs(z-111)>1:raise ValueError(f'not 111m gate: {z}')
                units=f['time'].attrs['units'];units=units.decode() if isinstance(units,bytes) else str(units)
                stamps=pd.Timestamp(units.split(' since ')[1],tz='UTC')+pd.to_timedelta(f['time'][:],unit='m')
                for ts,u,v in zip(stamps,f['u'][s,:,k],f['v'][s,:,k]):
                    if np.isfinite(u) and np.isfinite(v):rows.append((ts.isoformat(),float(u),float(v),z))
    frame=pd.DataFrame(rows,columns=['valid_end_utc','u','v','z_agl'])
    if frame.empty:raise ValueError(f'no PALUPD observations in {ym}')
    frame=frame.drop_duplicates('valid_end_utc').sort_values('valid_end_utc')
    frame['speed_ms']=np.hypot(frame.u,frame.v)
    tmp=dest.with_suffix('.partial');frame.to_csv(tmp,index=False);tmp.replace(dest)
    print('OBS_MONTH',ym,'rows',len(frame),'bytes',len(response.content),'seconds',round(time.monotonic()-t,2),flush=True)
print('OBS_ALL_DONE',flush=True)
