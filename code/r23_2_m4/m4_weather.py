#!/usr/bin/env python3
"""Classify OKC test 10-minute rows using METAR TS/VCTS/CB within 25 km and ±1h.
IEM routine+special reports (report_type 3/4), yearly output only on Colab.
"""
import io,json,re,math
from pathlib import Path
import numpy as np,pandas as pd
from m4_training import get
ROOT=Path('/content/m4/OKC');ROOT.mkdir(parents=True,exist_ok=True)
NEIGHBORS={'GOK':['GOK'],'OKC':['OKC','OUN','PWA','RCE','TIK'],'PWA':['HSD','OKC','PWA','RCE']}
ALL=sorted({s for values in NEIGHBORS.values() for s in values})
url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
files=[]
for month in pd.date_range('2023-01-01','2024-01-01',freq='MS',inclusive='left',tz='UTC'):
    end=month+pd.DateOffset(months=1)
    p=ROOT/f'weather_{month:%Y%m}.csv'
    if not p.exists():
        par=[('station',s) for s in ALL]+[('data','metar'),('data','wxcodes'),('year1',month.year),('month1',month.month),('day1',1),('year2',end.year),('month2',end.month),('day2',1),('tz','Etc/UTC'),('format','onlycomma'),('latlon','no'),('elev','no'),('missing','M'),('trace','T'),('direct','no'),('report_type',3),('report_type',4)]
        r=get(url,params=par);df=pd.read_csv(io.StringIO(r.text));assert {'station','valid','metar','wxcodes'}<=set(df)
        q=p.with_suffix('.partial');df.to_csv(q,index=False);q.rename(p)
    files.append(p);print('WEATHER_MONTH',month.strftime('%Y%m'),p.stat().st_size,flush=True)
raw=pd.concat([pd.read_csv(p) for p in files],ignore_index=True)
raw['valid']=pd.to_datetime(raw.valid,utc=True)
# METAR weather group includes TS/-TSRA/VCTS. Cloud layer with CB suffix qualifies.
def ts_cb(row):
    report=str(row.metar).upper().split(' RMK ')[0]
    tokens=[已隐去]
    return any(re.search(r'(^|[-+])TS|VCTS',token) for token in tokens) or any(re.match(r'^(FEW|SCT|BKN|OVC)\d{3}CB$',token) for token in tokens)
raw['flag']=raw.apply(ts_cb,axis=1)
raw[raw.flag][['station','valid','metar','wxcodes']].to_csv(ROOT/'weather_positive_reports.csv',index=False)
obs=pd.concat([pd.read_csv(p) for p in sorted((ROOT/'obs_test').glob('*.csv'))],ignore_index=True)
obs['valid_end_utc']=pd.to_datetime(obs.valid_end_utc,utc=True)
rows=[]
for site,frame in obs.groupby('station'):
    times=np.sort(raw.loc[raw.station.isin(NEIGHBORS[site])&raw.flag,'valid'].to_numpy(dtype='datetime64[ns]'))
    for t in frame.valid_end_utc:
        value=np.datetime64(t.tz_localize(None))
        idx=np.searchsorted(times,value)
        near=any(0<=j<len(times) and abs((times[j]-value).astype('timedelta64[s]').astype(int))<=3600 for j in (idx-1,idx))
        rows.append((site,t,bool(near)))
pd.DataFrame(rows,columns=['site','valid_end_utc','convective']).drop_duplicates(['site','valid_end_utc']).to_csv(ROOT/'weather_test.csv',index=False)
print('WEATHER_DONE',len(rows),sum(x[2] for x in rows),'source',url,flush=True)
