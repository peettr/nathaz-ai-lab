import io,re,json
from pathlib import Path
import requests,pandas as pd
R=Path(__file__).resolve().parent;H3=R.parent/'h3'
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
rows=[]; sources=[]
listing=requests.get(base,timeout=60).text
for year in range(2020,2026):
    files=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',listing)))
    if not files:raise RuntimeError(f'NOAA {year} missing')
    name=files[-1];src=H3/name
    if src.exists():d=pd.read_csv(src,low_memory=False)
    else:
        u=base+name;resp=requests.get(u,timeout=180);resp.raise_for_status();d=pd.read_csv(io.BytesIO(resp.content),compression='gzip',low_memory=False)
    a=d[(d.STATE=='TEXAS')&(d.EVENT_TYPE=='Thunderstorm Wind')&d.BEGIN_LAT.between(31.5,34)&d.BEGIN_LON.between(-98.5,-95.5)].copy()
    a['utc']=pd.to_datetime(a.BEGIN_DATE_TIME,errors='coerce').dt.tz_localize('America/Chicago',ambiguous='NaT',nonexistent='shift_forward').dt.tz_convert('UTC')
    rows.append(a[['EVENT_ID','BEGIN_DATE_TIME','utc','BEGIN_LAT','BEGIN_LON','MAGNITUDE']]);sources.append(base+name)
raw=pd.concat(rows,ignore_index=True);raw.to_csv(R/'storm_reports_h4.csv',index=False)
c=raw.groupby(raw.utc.dt.strftime('%Y-%m-%d')).agg(reports=('EVENT_ID','size'),first=('utc','min'),last=('utc','max')).sort_values(['reports','first'],ascending=[False,True]);c.to_csv(R/'candidate_dates_h4.csv')
chosen=[]
for day in ['2024-06-01','2025-07-09']:
    if day in c.index:chosen.append(day)
for day in c.index:
    if len(chosen)>=5:break
    if day not in chosen:chosen.append(day)
(R/'events_h4.json').write_text(json.dumps({'chosen_utc_dates':chosen,'preferred_dates':{'2024-06-01':int(c.loc['2024-06-01','reports']) if '2024-06-01' in c.index else 0,'2025-07-09':int(c.loc['2025-07-09','reports']) if '2025-07-09' in c.index else 0},'sources':sources,'selection':'TX Thunderstorm Wind reports within DFW box by UTC date, prefer named dates if present, then top counts'},indent=2))
print('top candidate days\n',c.head(15).to_string());print('chosen',chosen)
