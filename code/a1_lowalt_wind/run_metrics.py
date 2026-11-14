#!/usr/bin/env python3
"""Evaluate station-matched wind forecasts. Requires licensed observations as input.

Input CSV columns: station,init_utc,lead_h,source,obs_speed,obs_dir,obs_gust,
fc_u,fc_v. One row per station/init/lead/source. Times UTC ISO8601.
This module NEVER downloads or exports observations. Run only on a permitted host.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

LEADS = [6, 12, 24, 36, 48, 72]
WIND_THRESH = [6, 8, 10, 12]
GUST_THRESH = [10, 13, 15]

def circular_error(a, b):
    return np.abs((a - b + 180) % 360 - 180)

def fit_linear(x, y):
    good = np.isfinite(x) & np.isfinite(y)
    if good.sum() < 12 or np.std(x[good]) < 1e-8:
        return (float(np.nanmean(y[good])), 0.) if good.sum() else (np.nan, np.nan)
    b, a = np.polyfit(x[good], y[good], 1)
    return float(a), float(b)

def skill(y, p, direction=None, pred_direction=None):
    good = np.isfinite(y) & np.isfinite(p)
    if not good.any():
        return dict(n=0, mae=None, bias=None, dir_mae=None)
    de = None
    if direction is not None and pred_direction is not None:
        dgood = good & np.isfinite(direction) & np.isfinite(pred_direction)
        de = float(np.mean(circular_error(direction[dgood], pred_direction[dgood]))) if dgood.any() else None
    return dict(n=int(good.sum()), mae=float(np.mean(np.abs(p[good]-y[good]))),
                bias=float(np.mean(p[good]-y[good])), dir_mae=de)

def event(y, p, threshold):
    good = np.isfinite(y) & np.isfinite(p)
    o = y[good] >= threshold
    f = p[good] >= threshold
    hit = int((o & f).sum()); miss = int((o & ~f).sum()); false = int((~o & f).sum())
    return dict(n=int(good.sum()), events=int(o.sum()), hit_rate=hit/(hit+miss) if hit+miss else None,
                false_alarm_ratio=false/(hit+false) if hit+false else None,
                csi=hit/(hit+miss+false) if hit+miss+false else None,
                brier=float(np.mean((f.astype(float)-o.astype(float))**2)) if good.any() else None,
                hits=hit, misses=miss, false_alarms=false)

def build_predictions(df):
    df = df.copy()
    df['init_utc'] = pd.to_datetime(df['init_utc'], utc=True)
    df['valid_utc'] = df.init_utc + pd.to_timedelta(df.lead_h, unit='h')
    df['fc_speed'] = np.hypot(df.fc_u, df.fc_v)
    df['fc_dir'] = (270 - np.degrees(np.arctan2(df.fc_v, df.fc_u))) % 360
    df['month'] = df.valid_utc.dt.month
    df['hour'] = df.valid_utc.dt.hour
    cutoff = df.init_utc.min() + pd.DateOffset(months=8)
    end = df.init_utc.min() + pd.DateOffset(months=12)
    df['part'] = np.where(df.init_utc < cutoff, 'train', np.where(df.init_utc < end, 'test', 'outside'))
    if df[df.part=='test'].empty or df[df.part=='train'].empty:
        raise ValueError('Need 12 months of paired forecasts (first 8 training, next 4 testing).')
    # All sources use identical station/lead speed calibration and gust regression.
    df['corrected'] = np.nan; df['gust_pred'] = np.nan
    for (s, lead, source), group in df.groupby(['station','lead_h','source']):
        tr = group[group.part=='train']; te = group[group.part=='test']
        if tr.empty or te.empty: continue
        a,b = fit_linear(tr.fc_speed.to_numpy(), tr.obs_speed.to_numpy())
        z = np.maximum(0, a+b*group.fc_speed.to_numpy())
        df.loc[group.index, 'corrected'] = z
        # gust fit uses corrected speed on TRAIN only (no test leakage).
        atr,btr = fit_linear(np.maximum(0,a+b*tr.fc_speed.to_numpy()),tr.obs_gust.to_numpy())
        df.loc[group.index, 'gust_pred'] = np.maximum(0,atr+btr*z)
    # Persistence: nearest exact initialization observation, independent of source.
    obs = df[['station','valid_utc','obs_speed','obs_dir','obs_gust']].drop_duplicates(['station','valid_utc'])
    obs = obs.rename(columns={'valid_utc':'init_utc','obs_speed':'persistence','obs_dir':'persistence_dir','obs_gust':'persistence_gust'})
    df = df.merge(obs, on=['station','init_utc'],how='left',validate='many_to_one')
    # Climatology from TRAIN observations only, grouped station/calendar month/UTC hour.
    climat = (df[df.part=='train'].drop_duplicates(['station','valid_utc'])
              .groupby(['station','month','hour'])[['obs_speed','obs_gust']].mean()
              .rename(columns={'obs_speed':'climatology','obs_gust':'climatology_gust'}))
    df = df.join(climat, on=['station','month','hour'])
    return df, cutoff, end

def summarize(df):
    records=[]
    for (source,lead), group in df[df.part=='test'].groupby(['source','lead_h']):
        y=group.obs_speed.to_numpy(); direction=group.obs_dir.to_numpy()
        for variant,col in [('raw','fc_speed'),('corrected','corrected')]:
            p=group[col].to_numpy()
            r=dict(source=source,lead_h=int(lead),variant=variant,**skill(y,p,direction,group.fc_dir.to_numpy()))
            for t in WIND_THRESH: r[f'wind_{t}']=event(y,p,t)
            if variant=='corrected':
                for t in GUST_THRESH: r[f'gust_{t}']=event(group.obs_gust.to_numpy(),group.gust_pred.to_numpy(),t)
            records.append(r)
    # Baselines are calculated from ONE reference source only to avoid duplication.
    reference=df[df.source==sorted(df.source.unique())[0]]
    for lead, group in reference[reference.part=='test'].groupby('lead_h'):
        for name,col,dc,gc in [('persistence','persistence','persistence_dir','persistence_gust'),
                               ('climatology','climatology',None,'climatology_gust')]:
            y=group.obs_speed.to_numpy(); p=group[col].to_numpy()
            r=dict(source=name,lead_h=int(lead),variant='baseline',**skill(y,p,group.obs_dir.to_numpy(),group[dc].to_numpy() if dc else None))
            for t in WIND_THRESH:r[f'wind_{t}']=event(y,p,t)
            for t in GUST_THRESH:r[f'gust_{t}']=event(group.obs_gust.to_numpy(),group[gc].to_numpy(),t)
            records.append(r)
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paired',required=True,help='Licensed station-paired CSV; not exported')
    p.add_argument('--out',required=True)
    p.add_argument('--sources',nargs='+',required=True)
    p.add_argument('--seed',type=int,default=20261014)
    p.add_argument('--bootstrap',type=int,default=1000)
    p.add_argument('--min-stations',type=int,default=8)
    a=p.parse_args()
    df=pd.read_csv(a.paired)
    needed={'station','init_utc','lead_h','source','obs_speed','obs_dir','obs_gust','fc_u','fc_v'}
    if needed-set(df.columns):raise ValueError(f'Missing columns: {needed-set(df.columns)}')
    df=df[df.source.isin(a.sources) & df.lead_h.isin(LEADS)].copy()
    if df.station.nunique()<a.min_stations:raise ValueError('Insufficient stations; no gate verdict.')
    if df.duplicated(['station','init_utc','lead_h','source']).any():raise ValueError('Duplicate station/init/lead/source')
    df,cutoff,end=build_predictions(df)
    records=summarize(df)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    payload=dict(period=dict(train_end=cutoff.isoformat(),test_end=end.isoformat()),stations=sorted(df.station.unique()),
                 records=records, caveat='No verdict unless full coverage, common-case matching, and license verified.')
    (out/'metrics.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'rows':len(df),'test_rows':int((df.part=='test').sum()),'records':len(records),'metrics':str(out/'metrics.json')}))
if __name__=='__main__':main()
