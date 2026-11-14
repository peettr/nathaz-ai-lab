#!/usr/bin/env python3
"""R23.7 preregistered M1 power gate, 2022 inputs only, executed on Colab CPU."""
import json, pathlib, datetime
import numpy as np, pandas as pd
ROOT=pathlib.Path('/content/r237m1v2')
OLD=pathlib.Path('/content/r237_old')
SRCS=('GRAP_v100_GFS','GRAP_v100_IFS','PANG_v100_GFS','PANG_v100_IFS','GFS','HRES')
KEY=['station','init_utc','lead_h']
def lin(x,y):
    m=np.isfinite(x)&np.isfinite(y)
    if m.sum()<12:return [float(np.nanmean(y[m])),0.] if m.any() else [np.nan,np.nan]
    if np.std(x[m])<1e-8:return [float(np.mean(y[m])),0.]
    b,a=np.polyfit(x[m],y[m],1)
    return [float(a),float(b)]
def main():
    originals=pd.read_csv(OLD/'paired_station_train.csv.gz')
    originals=originals[originals.source.isin(SRCS)&originals.lead_h.eq(24)].copy()
    extra=pd.concat([pd.read_csv(ROOT/f'{s}_station_v1.csv.gz') for s in ('GRAP_v100_IFS','PANG_v100_IFS')]+[pd.read_csv(ROOT/'HRES_2022_station_v1.csv.gz')],ignore_index=True)
    extra=extra[extra.lead_h.eq(24)].copy()
    for frame in (originals,extra):
        frame['init_utc']=pd.to_datetime(frame.init_utc,utc=True,format='mixed')
        frame['valid_utc']=frame.init_utc+pd.to_timedelta(frame.lead_h,unit='h')
        assert not frame.duplicated(KEY+['source']).any()
    # Only old 2022 observation-target pairs; no new 2023 data.
    obs=originals[originals.source=='GFS'][KEY+['valid_utc','metar_speed']].copy()
    assert not obs.duplicated(KEY).any()
    raw=pd.concat([originals[KEY+['source','fc_u','fc_v']],extra[KEY+['source','fc_u','fc_v']]],ignore_index=True)
    assert set(raw.source)==set(SRCS)
    a=raw.merge(obs,on=KEY,how='inner',validate='many_to_one')
    c=a.groupby(KEY).source.nunique(); keys=c[c==len(SRCS)].index
    a=a.set_index(KEY).loc[keys].reset_index()
    assert all(a.groupby(KEY).source.nunique()==len(SRCS)) and a.source.value_counts().nunique()==1
    assert a.metar_speed.notna().all() and (a.valid_utc.dt.year==2022).all()
    a['raw']=np.hypot(a.fc_u,a.fc_v)
    a['corrected']=np.nan; coeff={}
    for (station,src),g in a.groupby(['station','source']):
        fit=lin(g.raw.to_numpy(),g.metar_speed.to_numpy())
        coeff[f'{station}:{src}']=fit
        a.loc[g.index,'corrected']=np.maximum(0,fit[0]+fit[1]*g.raw.to_numpy())
    assert a.corrected.notna().all()
    # Each station-key contributes one paired error per arm; a bootstrap day keeps all six arms paired.
    a['day']=a.valid_utc.dt.floor('D')
    days=pd.Index(sorted(a.day.unique()));n22=len(days)
    by=a.groupby(['source','day']).apply(lambda g:pd.Series({'sse':np.abs(g.corrected-g.metar_speed).sum(),'n':len(g)}),include_groups=False)
    sums={s:by.loc[s].reindex(days).sse.to_numpy() for s in SRCS}
    counts=by.loc[SRCS[0]].reindex(days).n.to_numpy()
    assert all(np.array_equal(by.loc[s].reindex(days).n.to_numpy(),counts) for s in SRCS)
    def val(w):
        maes={s:(w@sums[s])/(w@counts) for s in SRCS}
        dgc=maes['GRAP_v100_GFS']/maes['GRAP_v100_IFS']-1
        dpg=maes['PANG_v100_GFS']/maes['PANG_v100_IFS']-1
        return dgc-dpg
    point=float(val(np.ones(n22)))
    rng=np.random.default_rng(20261108)
    weights=rng.multinomial(n22,np.full(n22,1/n22),size=1000)
    draws=np.array([val(w) for w in weights]);ci=np.quantile(draws,[.025,.975]);h22=float((ci[1]-ci[0])/2)
    n23=(datetime.date(2023,12,31)-datetime.date(2023,1,18)).days+1
    h23=float(h22*np.sqrt(n22/n23))
    result={'criterion':'h23 > 0.03 => no resolution; otherwise proceed','sample':'2022 24h six-arm paired, corrected in-sample per station/source','paired_station_keys':len(keys),'rows_per_source':int(a.source.value_counts().iloc[0]),'N22_verification_days':n22,'N23_calendar_days_2023_01_18_to_12_31':n23,'C22_point':point,'C22_bootstrap_ci95':ci.tolist(),'h22':h22,'h23':h23,'seed':20261108,'draws':1000,'no_resolution':bool(h23>0.03),'pass':bool(h23<=0.03),'source_row_counts':{k:int(v) for k,v in a.source.value_counts().items()},'coefficients':coeff,'2023_IFS_or_HRES_opened':False}
    with (ROOT/'power_gate_v1.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print('POWER_GATE',json.dumps({k:v for k,v in result.items() if k!='coefficients'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
