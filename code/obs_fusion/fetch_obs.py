#!/usr/bin/env python3
"""IEM TX_ASOS station metadata and cold-season hourly METAR; NCEI storm exclusion."""
import io,json,re,gzip,requests
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
S=requests.Session(); S.headers['User-Agent']='NatHaz-AI-Lab-observation-fusion/1.0'
network='https://mesonet.agron.iastate.edu/geojson/network.py?network=TX_ASOS'
f=S.get(network,timeout=60); f.raise_for_status()
rows=[]
for x in f.json()['features']:
 lon,lat=x['geometry']['coordinates']; p=x['properties']
 if 28<=lat<=34 and -100<=lon<=-94 and (not p.get('archive_begin') or p['archive_begin']<='2020-11-01'):
  rows.append(dict(station=x['id'],lat=lat,lon=lon,elevation_m=p.get('elevation'),name=p.get('sname')))
st=pd.DataFrame(rows).sort_values('station');st.to_csv(ROOT/'stations.csv',index=False)
print('stations',len(st),flush=True)
allrows=[]; ledger=[]
for month in pd.date_range('2020-11-01','2021-03-01',freq='MS'):
 end=month+pd.offsets.MonthBegin()
 for group in range(0,len(st),40):
  ids=st.station.iloc[group:group+40].tolist()
  p={'station':','.join(ids),'sts':(month-pd.Timedelta(days=1)).strftime('%Y-%m-%dT00:00Z'),'ets':(end+pd.Timedelta(days=1)).strftime('%Y-%m-%dT00:00Z'),'tz':'UTC','format':'onlycomma','data':'sknt,drct,metar','report_type':'3,4'}
  r=S.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py',params=p,timeout=240);r.raise_for_status()
  df=pd.read_csv(io.StringIO(r.text),comment='#',low_memory=False)
  if not {'station','valid','sknt','drct','metar'}.issubset(df):raise ValueError((r.url,r.text[:300]))
  df['valid']=pd.to_datetime(df.valid,utc=True,errors='coerce');df=df[(df.valid>=month.tz_localize('UTC'))&(df.valid<end.tz_localize('UTC'))].copy()
  allrows.append(df);ledger.append(dict(url=r.url,bytes=len(r.content),records=len(df)))
  print(month.strftime('%Y-%m'),group,len(df),flush=True)
raw=pd.concat(allrows,ignore_index=True);raw.to_csv(ROOT/'metar_raw.csv.gz',index=False,compression='gzip')
raw['sknt']=pd.to_numeric(raw.sknt,errors='coerce');raw['drct']=pd.to_numeric(raw.drct,errors='coerce')
raw['hour']=(raw.valid+pd.Timedelta(minutes=30)).dt.floor('h')
raw['minute_distance']=(raw.valid-raw.hour).abs()
raw=raw.sort_values(['station','hour','minute_distance','valid']).drop_duplicates(['station','hour'])
raw=raw[raw.sknt.between(0,150)].copy();raw['speed']=raw.sknt*0.5144444444444445
raw['ts_cb']=raw.metar.fillna('').str.split(' RMK ').str[0].str.contains(r'(?<![A-Z])(?:[+-]?TS[A-Z]*|VCTS|[A-Z]{3}[0-9]{3}CB)(?![A-Z])|\b(?:SCT|BKN|OVC|FEW)\d{3}CB\b',regex=True)
raw[['station','hour','speed','drct','ts_cb']].to_csv(ROOT/'observations.csv.gz',index=False,compression='gzip')
(ROOT/'observation_ledger.json').write_text(json.dumps(ledger,indent=2))
print('hourly',len(raw), 'TS',raw.ts_cb.sum(),flush=True)
# Storm Events: national annual files; dates excluded conservatively when any TX Thunderstorm Wind anywhere.
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
page=S.get(base,timeout=60).text
storm=[]
for year in (2020,2021):
 files=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',page)))
 if not files: raise RuntimeError('storm archive index unavailable')
 url=base+files[-1];rr=S.get(url,timeout=240);rr.raise_for_status()
 (ROOT/files[-1]).write_bytes(rr.content)
 data=pd.read_csv(io.BytesIO(gzip.decompress(rr.content)),low_memory=False)
 sub=data[(data.STATE=='TEXAS')&(data.EVENT_TYPE=='Thunderstorm Wind')]
 storm.extend(sub.BEGIN_DATE_TIME.astype(str).tolist())
 ledger.append(dict(url=url,bytes=len(rr.content),records=len(sub)))
 print('storm',year,len(sub),flush=True)
(ROOT/'storm_dates.json').write_text(json.dumps(sorted(set(pd.to_datetime(storm,errors='coerce').strftime('%Y-%m-%d'))),indent=2))
(ROOT/'observation_ledger.json').write_text(json.dumps(ledger,indent=2))
