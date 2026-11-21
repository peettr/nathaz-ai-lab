#!/usr/bin/env python3
"""Fetch public IEM NCEI ASOS 1-minute + METAR fallbacks; output hourly station series.
Usage: python run_observations.py --stations stations.csv --year 2023 --out /content/a1/obs.csv
"""
import argparse, io, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import requests
KNOT = 0.5144444444444445
URL1 = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py'
URL2 = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
S = requests.Session(); S.headers['User-Agent']='NatHaz-A1-research (public ASOS retrieval)'
def get(url, p):
    for i in range(4):
        try:
            r=S.get(url,params=p,timeout=180)
        except requests.RequestException:
            if i==3:raise
            time.sleep(5*(i+1));continue
        if r.status_code==200: return r
        if r.status_code not in (429,503,504): raise RuntimeError(f'{r.url}: {r.status_code} {r.text[:150]}')
        time.sleep(5*(i+1))
    raise RuntimeError(f'ASOS source unavailable: {r.status_code}')
def hourly_minute(df,stations,hours):
    if df.empty:return pd.DataFrame()
    df=df.rename(columns={'valid(UTC)':'valid_utc'})
    df['valid_utc']=pd.to_datetime(df.valid_utc,utc=True,errors='coerce')
    for k in ('sknt','drct','gust_sknt'):df[k]=pd.to_numeric(df[k],errors='coerce')
    df['sknt']=df.sknt.where(df.sknt>=0)
    df['gust_sknt']=df.gust_sknt.where(df.gust_sknt>=0)
    df['drct']=df.drct.where(df.drct.between(0,360))
    df=df[df.station.isin(stations)].copy()
    df['hour']=(df.valid_utc+pd.Timedelta(minutes=30)).dt.floor('h')
    angle=np.deg2rad(df.drct)
    df['u']=-df.sknt*np.sin(angle)*KNOT;df['v']=-df.sknt*np.cos(angle)*KNOT
    agg=df.groupby(['station','hour']).agg(obs_speed=('sknt','mean'),obs_gust=('gust_sknt','max'),obs_u=('u','mean'),obs_v=('v','mean'),obs_count=('sknt','count')).reset_index()
    agg=agg[agg.obs_count>=30].rename(columns={'hour':'valid_utc'})
    agg=agg[agg.valid_utc.isin(hours)].copy()
    agg['obs_speed']*=KNOT;agg['obs_gust']*=KNOT
    agg['obs_dir']=(270-np.rad2deg(np.arctan2(agg.obs_v,agg.obs_u)))%360
    agg.loc[np.hypot(agg.obs_u,agg.obs_v)<.05,'obs_dir']=np.nan
    agg['obs_method']='NCEI_1min_IEM'
    return agg[['station','valid_utc','obs_speed','obs_dir','obs_gust','obs_u','obs_v','obs_count','obs_method']]
def hourly_metar(df,stations,hours):
    if df.empty:return pd.DataFrame()
    df['valid_utc']=pd.to_datetime(df.valid,utc=True,errors='coerce')
    for k in ('sknt','drct','gust'):df[k]=pd.to_numeric(df[k],errors='coerce')
    df['drct']=df.drct.where(df.drct.between(0,360));df['sknt']=df.sknt.where(df.sknt>=0)
    df=df[df.station.isin(stations)&df.sknt.notna()].copy()
    df['hour']=(df.valid_utc+pd.Timedelta(minutes=30)).dt.floor('h')
    df['distance']=(df.valid_utc-df.hour).abs()
    df=df.sort_values(['station','hour','distance','valid_utc']).drop_duplicates(['station','hour']).rename(columns={'hour':'valid_utc_hour'})
    df=df[df.valid_utc_hour.isin(hours)].copy()
    df['obs_speed']=df.sknt*KNOT;df['obs_gust']=df.gust*KNOT;df['obs_dir']=df.drct
    df['obs_u']=-df.obs_speed*np.sin(np.deg2rad(df.drct));df['obs_v']=-df.obs_speed*np.cos(np.deg2rad(df.drct))
    df['obs_count']=1;df['obs_method']='IEM_METAR_nearest_2min'
    return df.rename(columns={'valid_utc':'metar_utc','valid_utc_hour':'valid_utc'})[['station','valid_utc','obs_speed','obs_dir','obs_gust','obs_u','obs_v','obs_count','obs_method']]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stations',required=True);ap.add_argument('--year',type=int,required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    stations=pd.read_csv(a.stations).station.tolist(); start=pd.Timestamp(f'{a.year}-01-01',tz='UTC');end=pd.Timestamp(f'{a.year+1}-01-04',tz='UTC')
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    rows=[];ledger=[]
    for begin in pd.date_range(start,end,freq='MS',tz='UTC'):
        finish=min(begin+pd.DateOffset(months=1),end)
        if finish<=begin:continue
        # IEM one-minute API interprets sts/ets in central time even when UTC requested; request broad envelope and filter UTC.
        x0=begin-pd.Timedelta(hours=10);x1=finish+pd.Timedelta(hours=10)
        p={'station':','.join(stations),'sts':x0.strftime('%Y-%m-%dT%H:%MZ'),'ets':x1.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','what':'download','delim':'comma','sample':'1min','vars':'sknt,drct,gust_sknt'}
        t=time.monotonic();r=get(URL1,p);minute=pd.read_csv(io.StringIO(r.text));hours=pd.date_range(begin,finish-pd.Timedelta(hours=1),freq='h',tz='UTC')
        one=hourly_minute(minute,stations,hours);print('minute',begin.date(),len(minute),len(one),round(time.monotonic()-t,1),flush=True)
        ledger.append({'month':str(begin.date()),'source':'NCEI_1min_IEM','bytes':len(r.content),'seconds':time.monotonic()-t,'url':r.url})
        # METAR bulk includes station coverage beyond the three available minute sites.
        p={'station':','.join(stations),'sts':x0.strftime('%Y-%m-%dT%H:%MZ'),'ets':x1.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','format':'onlycomma','data':'sknt,drct,gust','missing':'M','report_type':'3,4'}
        t=time.monotonic();r=get(URL2,p);met=pd.read_csv(io.StringIO(r.text),comment='#');fallback=hourly_metar(met,stations,hours)
        ledger.append({'month':str(begin.date()),'source':'IEM_METAR','bytes':len(r.content),'seconds':time.monotonic()-t,'url':r.url})
        print('METAR',begin.date(),len(met),len(fallback),round(time.monotonic()-t,1),flush=True)
        month=pd.concat([one,fallback],ignore_index=True).drop_duplicates(['station','valid_utc'],keep='first')
        rows.append(month)
        pd.concat(rows).to_csv(out,index=False)
        (out.parent/'observation_ledger.json').write_text(json.dumps(ledger,indent=2))
    df=pd.concat(rows).drop_duplicates(['station','valid_utc'])
    print('OBS_DONE',len(df),df.groupby(['station','obs_method']).size().to_dict(),out,flush=True)
if __name__=='__main__':main()
