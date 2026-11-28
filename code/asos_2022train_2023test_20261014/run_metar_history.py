#!/usr/bin/env python3
"""Retrieve IEM public METAR station observations by month, 2013–2023.
No METAR gust verification: METAR gust is conditional/selected reporting.
"""
import argparse,io,json,time,traceback,os
from pathlib import Path
import pandas as pd
from run_observations import get,URL2,hourly_metar

def main():
 p=argparse.ArgumentParser();p.add_argument('--stations',required=True);p.add_argument('--start-year',type=int,default=2013);p.add_argument('--end-year',type=int,default=2023);p.add_argument('--out',required=True);a=p.parse_args()
 stations=pd.read_csv(a.stations).station.tolist();root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
 for year in range(a.start_year,a.end_year+1):
  for m in range(1,13):
   begin=pd.Timestamp(year=year,month=m,day=1,tz='UTC');finish=begin+pd.DateOffset(months=1)
   target=root/f'metar_{year}_{m:02}.csv';meta=root/f'metar_{year}_{m:02}.json'
   if target.exists() and meta.exists():continue
   if target.exists() or meta.exists():raise RuntimeError(f'partial existing {target}')
   x0=begin-pd.Timedelta(hours=10);x1=finish+pd.Timedelta(hours=10)
   q={'station':','.join(stations),'sts':x0.strftime('%Y-%m-%dT%H:%MZ'),'ets':x1.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','format':'onlycomma','data':'sknt,drct,gust','missing':'M','report_type':'3,4'}
   t=time.monotonic()
   r=get(URL2,q)
   raw=pd.read_csv(io.StringIO(r.text),comment='#')
   hours=pd.date_range(begin,finish-pd.Timedelta(hours=1),freq='h',tz='UTC')
   sample=hourly_metar(raw,stations,hours)
   tmp=target.with_suffix('.part');sample.to_csv(tmp,index=False);os.replace(tmp,target)
   meta.write_text(json.dumps({'year':year,'month':m,'url':r.url,'response_bytes':len(r.content),'seconds':time.monotonic()-t,'raw_rows':len(raw),'hourly_rows':len(sample),'station_counts':sample.station.value_counts().to_dict()}))
   print('MONTH',year,m,len(raw),len(sample),len(r.content),round(time.monotonic()-t,1),flush=True)
 print('METAR_DONE',a.start_year,a.end_year,flush=True)
if __name__=='__main__':main()
