import csv,io,datetime as dt,os,sys
os.environ['SITE_STAGE_ROOT']='/content/site_stage_v2';sys.path.insert(0,'/content');import run_colab as c
for st,t in [('KCRW',dt.datetime(2012,12,23,18,38)),('KABR',dt.datetime(2013,1,11,21,43))]:
 u=c.query(st,t-dt.timedelta(hours=2),t+dt.timedelta(hours=2))
 with c.fetch(u) as resp:rows=list(csv.DictReader(io.TextIOWrapper(resp,encoding='utf8',errors='replace')))
 print('\n',st,t,'rows',len(rows))
 for x in rows:
  if (z:=c.parse(x['valid'])) and abs((z-t).total_seconds())<=3600 and (c.num(x.get('gust')) or c.num(x.get('peak_wind_gust'))):print(x['valid'],x.get('gust'),x.get('peak_wind_gust'),x.get('peak_wind_time'),x.get('metar'))
