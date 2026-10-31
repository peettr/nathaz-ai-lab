#!/usr/bin/env python3
"""Post-Swiss Paris side-arm only; train June–October 2023, test November–February.
Runs on Colab CPU. Does not modify the frozen Swiss scorer/configuration.
"""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
ROOT=Path('/content/m5'); OUT=ROOT/'paris_output'; OUT.mkdir(exist_ok=True)
FHRS=(6,12,24,48); METHODS=('R100','H_log','H_2seg_60','H_2seg_100','H_2seg_200','M')
START=pd.Timestamp('2023-06-01T00:00Z');CUT=pd.Timestamp('2023-11-01T00:00Z');END=pd.Timestamp('2024-03-01T00:00Z')

def paired():
    paths=sorted((ROOT/'paris_gfs').glob('*.csv'))
    expected=len(pd.date_range('2023-05-30T00:00Z','2024-02-29T18:00Z',freq='6h'))
    if len(paths)!=expected:raise ValueError(f'GFS incomplete {len(paths)}/{expected}')
    fc=pd.concat(map(pd.read_csv,paths),ignore_index=True)
    fc['init_utc']=pd.to_datetime(fc.init_utc,utc=True)
    fc['valid_end_utc']=fc.init_utc+pd.to_timedelta(fc.fhr,unit='h')
    fc=fc[(fc.valid_end_utc>=START)&(fc.valid_end_utc<END)].copy()
    fc['issue_utc']=fc.init_utc+pd.Timedelta(hours=4)
    fc['info_cutoff_utc']=fc.issue_utc
    if (fc.info_cutoff_utc>fc.issue_utc).any() or (fc.issue_utc>fc.valid_end_utc).any():raise ValueError('future information')
    obs=pd.concat(map(pd.read_csv,sorted((ROOT/'paris_obs').glob('palupd_*.csv'))),ignore_index=True)
    obs.valid_end_utc=pd.to_datetime(obs.valid_end_utc,utc=True)
    obs=obs[['valid_end_utc','speed_ms']].rename(columns={'speed_ms':'obs'})
    if obs.valid_end_utc.duplicated().any():raise ValueError('duplicate observed valid end')
    d=fc.merge(obs,on='valid_end_utc',how='inner',validate='many_to_one')
    if d.empty or set(d.fhr)!=set(FHRS):raise ValueError('empty/missing lead pairs')
    u=d.u10.to_numpy();v=d.v10.to_numpy()
    d['R100']=np.hypot(d.u100,d.v100)
    d['H_log']=np.hypot(u,v)*np.log(111/.03)/np.log(10/.03)
    # A1 morphology v3: 10m wind × log(zb/z0ref)/log(10/z0ref)
    # × log((111-d)/z0)/log((zb-d)/z0), z0ref=0.03m.
    d['wind_from_deg']=(np.degrees(np.arctan2(-u,-v))+360)%360
    d['sector_from_deg']=((d.wind_from_deg+15)//30*30).astype(int)%360
    sectors=pd.read_csv(ROOT/'sectors.csv')[['sector_from_deg','d_m','z0_m']]
    d=d.merge(sectors,on='sector_from_deg',validate='many_to_one')
    for zb in (60,100,200):
        clearance=zb-d.d_m
        valid=(clearance>2*d.z0_m)&((111-d.d_m)>0)&(d.z0_m>0)
        d[f'H_2seg_{zb}']=np.where(valid,np.hypot(u,v)*np.log(zb/.03)/np.log(10/.03)*
                                 np.log((111-d.d_m)/d.z0_m)/np.log(clearance/d.z0_m),np.nan)
    for fhr in FHRS:
        train=d[(d.valid_end_utc<CUT)&(d.fhr==fhr)].dropna(subset=['R100','obs'])
        test=d[(d.valid_end_utc>=CUT)&(d.fhr==fhr)]
        if len(train)<200 or len(test)<100:raise ValueError(f'too few pairs fhr={fhr}: {len(train)}, {len(test)}')
        a,b=np.linalg.lstsq(np.column_stack([np.ones(len(train)),train.R100]),train.obs,rcond=None)[0]
        d.loc[d.fhr==fhr,'M']=a+b*d.loc[d.fhr==fhr,'R100']
    train=d[d.valid_end_utc<CUT].copy();test=d[d.valid_end_utc>=CUT].copy()
    if train.valid_end_utc.min()<START or test.valid_end_utc.max()>=END:raise ValueError('split')
    train.to_parquet(OUT/'paris_train_pairs.parquet',index=False)
    test.to_parquet(OUT/'paris_test_pairs.parquet',index=False)
    print('PARIS_PAIR',len(train),len(test),test.valid_end_utc.min(),test.valid_end_utc.max(),flush=True)
    return test

def stats(g):
    ret={};mae={}
    for method in METHODS:
        q=g.dropna(subset=[method,'obs']);mae[method]=float(np.abs(q[method]-q.obs).mean()) if len(q) else np.nan
        ret[f'MAE_{method}']=mae[method];ret[f'N_{method}']=len(q)
    den=mae['R100']-mae['M']
    for method in METHODS[1:-1]:ret[f'rho_{method}']=(mae['R100']-mae[method])/den if abs(den)>1e-12 else np.nan
    return ret

def main():
    test=paired(); rows=[];rng=np.random.default_rng(230507)
    for fhr,g in test.groupby('fhr'):
        g=g.copy();g['day']=g.valid_end_utc.dt.floor('D'); days=list(g.day.unique());blocks=[g[g.day==day] for day in days]
        if len(days)<30:raise ValueError('too few days')
        point=stats(g); draws=[]
        for _ in range(1000):
            b=pd.concat([blocks[i] for i in rng.integers(len(blocks),size=len(blocks))],ignore_index=True)
            draws.append(stats(b))
        for key,val in point.items():
            arr=np.array([q[key] for q in draws]);arr=arr[np.isfinite(arr)]
            rows.append({'fhr':int(fhr),'method_metric':key,'point':float(val),'lo':float(np.quantile(arr,.025)) if len(arr) else np.nan,
                         'hi':float(np.quantile(arr,.975)) if len(arr) else np.nan,'days':len(days),'draws_valid':len(arr)})
    pd.DataFrame(rows).to_csv(OUT/'paris_metrics.csv',index=False)
    (OUT/'paris_manifest.json').write_text(json.dumps({'source':'GFS AWS 0.25° range, PALUPD Zenodo 17710093 L3v1.42','test_rows':len(test),
        'method':'M OLS on R100 training only; H_2seg A1 morph_v3 sector coefficients; 1000 verifying-day blocks','site_lat_lon':[48.85,2.35]},indent=2))
    print('PARIS_SCORE_DONE',len(rows),flush=True)
if __name__=='__main__':main()
