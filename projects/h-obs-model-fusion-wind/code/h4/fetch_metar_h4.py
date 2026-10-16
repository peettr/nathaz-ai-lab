import io,json
from pathlib import Path
import requests,pandas as pd
R=Path(__file__).resolve().parent;sites=pd.read_csv(R/'stations_h4.csv');out=[]
for day in json.loads((R/'events_h4.json').read_text())['chosen_utc_dates']:
    tag=day.replace('-','');w=json.loads((R/f'window_{tag}_h4.json').read_text());start=pd.Timestamp(w['window_start']);end=pd.Timestamp(w['window_end'])
    p=dict(station=','.join(sites.station),sts=(start-pd.Timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(end+pd.Timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',format='onlycomma',data='sknt,gust,metar',report_type='3,4')
    resp=requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py',params=p,timeout=180);resp.raise_for_status();a=pd.read_csv(io.StringIO(resp.text),comment='#',low_memory=False);assert {'station','valid','sknt','gust','metar'}<=set(a.columns),(day,resp.text[:200]);a['event']=day;out.append(a)
    (R/f'iem_metar_url_{tag}_h4.txt').write_text(resp.url+'\n');print(day,'METAR',len(a), 'stations',a.station.nunique(),flush=True)
pd.concat(out,ignore_index=True).to_csv(R/'metar_crosscheck_h4.csv.gz',index=False,compression='gzip')
