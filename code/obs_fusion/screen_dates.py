#!/usr/bin/env python3
"""QC raw METAR and preselect cold-season windy days without region TS/CB."""
import json,re
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parent
x=pd.read_csv(R/'metar_raw.csv.gz',low_memory=False)
x['valid']=pd.to_datetime(x.valid,utc=True,errors='coerce')
x['hour']=(x.valid+pd.Timedelta(minutes=30)).dt.floor('h')
x['dist']=(x.valid-x.hour).abs()
x=x.sort_values(['station','hour','dist','valid']).drop_duplicates(['station','hour'])
x['sknt']=pd.to_numeric(x.sknt,errors='coerce');x=x[x.sknt.between(0,40)].copy()
x['speed']=x.sknt*0.5144444444444445
x['ts_cb']=x.metar.fillna('').str.split(' RMK ').str[0].str.contains(r'(?<![A-Z])(?:[+-]?TS[A-Z]*|VCTS)(?![A-Z])|\b(?:SCT|BKN|OVC|FEW)\d{3}CB\b',regex=True)
x['date']=x.hour.dt.strftime('%Y-%m-%d')
x[['station','hour','speed','drct','ts_cb','date']].to_csv(R/'observations_qc2.csv.gz',index=False,compression='gzip')
storm=set(json.loads((R/'storm_dates.json').read_text()))
a=x.groupby('date').agg(stations=('station','nunique'),n=('speed','size'),fraction8=('speed',lambda s:(s>=8).mean()),ts=('ts_cb','sum')).sort_values('fraction8',ascending=False)
print(a.head(45).to_string())
print('no ts and no TX storm');print(a[(a.stations>=60)&(a.ts==0)&(~a.index.isin(storm))].head(25).to_string())
