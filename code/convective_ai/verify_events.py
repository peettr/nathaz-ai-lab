"""Create candidate manifest and independently inspect IEM station gusts."""
import csv, gzip, io, re, urllib.request, urllib.parse, datetime, json
from pathlib import Path
IDS={'1089702':'DSM','1102083':'CNK','1114169':'SWO','1111438':'OFK','1203698':'DSM','1180878':'ALO','1107992':'LNK'}
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
INDEX=urllib.request.urlopen(BASE,timeout=60).read().decode()
found={}
for year in (2023,2024):
    name=re.search(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',INDEX).group()
    rows=csv.DictReader(io.StringIO(gzip.decompress(urllib.request.urlopen(BASE+name,timeout=120).read()).decode('utf-8-sig')))
    for r in rows:
        if r['EVENT_ID'] in IDS:found[r['EVENT_ID']]=(r,BASE+name)
for eid,station in IDS.items():
    if eid not in found: print('MISSING',eid);continue
    r,src=found[eid]
    local=datetime.datetime.strptime(r['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S')
    offset=int(re.search(r'-(\d+)',r['CZ_TIMEZONE']).group(1))
    utc=(local+datetime.timedelta(hours=offset)).replace(tzinfo=datetime.timezone.utc)
    start=utc-datetime.timedelta(hours=2);end=utc+datetime.timedelta(hours=2)
    args={'station':station,'sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust,peak_wind_time,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
    url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(args)
    try:
        body=urllib.request.urlopen(url,timeout=60).read().decode()
        obs=list(csv.DictReader(io.StringIO(body)))
        peak=sorted((x for x in obs if any(x.get(k,'M') not in ('M','') for k in ('gust','peak_wind_gust'))),key=lambda x:max((float(x.get(k)) for k in ('gust','peak_wind_gust') if x.get(k) not in ('M','')),default=0),reverse=True)[:3]
    except Exception as e: peak=[];print('IEM_ERROR',eid,repr(e))
    print(json.dumps({'id':eid,'station':station,'utc':utc.isoformat(),'ncei_kt':r['MAGNITUDE'],'source':r['SOURCE'],'location':r['BEGIN_LOCATION'],'lat':r['BEGIN_LAT'],'lon':r['BEGIN_LON'],'narrative':r['EVENT_NARRATIVE'],'ncei_url':src,'iem_url':url,'iem_top':peak},ensure_ascii=False))
