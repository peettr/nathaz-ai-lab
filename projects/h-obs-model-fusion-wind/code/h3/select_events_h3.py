import re,json,io
from pathlib import Path
import requests,pandas as pd
R=Path(__file__).resolve().parent
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
listing=requests.get(base,timeout=60).text
states=['TEXAS','OKLAHOMA','KANSAS','NEBRASKA','ARKANSAS','MISSOURI','LOUISIANA','NEW MEXICO','COLORADO']
allrows=[];sources=[]
for y in range(2018,2025):
 names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(y)+r'_c\d+\.csv\.gz',listing)))
 if not names: print('MISSING',y,flush=True);continue
 name=names[-1];p=R/name
 if not p.exists():
  resp=requests.get(base+name,timeout=180);resp.raise_for_status();p.write_bytes(resp.content)
 d=pd.read_csv(p,low_memory=False)
 d=d[d.STATE.isin(states)&d.EVENT_TYPE.isin(['High Wind','Thunderstorm Wind'])].copy()
 # NOAA BEGIN_DATE_TIME clock specified in CZ_TIMEZONE; convert US regional offsets with DST by state/local timezone.
 tzmap={'TEXAS':'America/Chicago','OKLAHOMA':'America/Chicago','KANSAS':'America/Chicago','NEBRASKA':'America/Chicago','ARKANSAS':'America/Chicago','MISSOURI':'America/Chicago','LOUISIANA':'America/Chicago','NEW MEXICO':'America/Denver','COLORADO':'America/Denver'}
 d['local']=pd.to_datetime(d.BEGIN_DATE_TIME,errors='coerce');d['utc']=pd.NaT
 for state,tz in tzmap.items():
  ix=d.STATE==state
  # BEGIN_DATE_TIME day format NOAA mm/dd/yyyy HH:MM:SS
  times=d.loc[ix,'local'].dt.tz_localize(tz,ambiguous='NaT',nonexistent='shift_forward').dt.tz_convert('UTC')
  d.loc[ix,'utc']=times.dt.tz_localize(None).values
 d['utc_date']=pd.to_datetime(d.utc).dt.date.astype(str)
 d['year']=y
 allrows.append(d[['year','STATE','EVENT_TYPE','utc_date','utc','BEGIN_LAT','BEGIN_LON','EVENT_ID']]);sources.append(base+name)
 print(y,len(d),flush=True)
raw=pd.concat(allrows,ignore_index=True);raw.to_csv(R/'storm_events_screen_h3.csv.gz',index=False,compression='gzip')
pivot=raw.groupby(['STATE','utc_date','EVENT_TYPE']).size().unstack(fill_value=0).reset_index()
for c in ['High Wind','Thunderstorm Wind']:
 if c not in pivot:pivot[c]=0
cand=pivot[(pivot['High Wind']>=5)&(pivot['Thunderstorm Wind']==0)].sort_values(['High Wind','utc_date'],ascending=[False,True]);cand.to_csv(R/'candidate_dates_h3.csv',index=False)
print(cand.head(60).to_string(index=False));(R/'storm_sources_h3.json').write_text(json.dumps(sources,indent=2))
