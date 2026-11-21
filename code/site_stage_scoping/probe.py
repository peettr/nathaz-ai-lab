"""Read-only small IEM station metadata and 2009/10 cold-season METAR coverage probe.
No raw observation files are saved. Hourly grid is UTC 00..23 and report_type=3 only.
"""
import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIONS = {'MSP':'MN','DSM':'IA','OMA':'NE','DTW':'MI','PIT':'PA','ALB':'NY','DFW':'TX','AUS':'TX','FSD':'SD','FAR':'ND','ICT':'KS','STL':'MO','IND':'IN','CLE':'OH','BDL':'CT'}
START = datetime(2009,10,1,tzinfo=timezone.utc)
END = datetime(2010,4,1,tzinfo=timezone.utc)
HEADERS = {'User-Agent':'AI-weather-research-station-feasibility/1.0'}
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),timeout=90) as r:
        return r.read().decode('utf-8')

rows=[]
for sid,state in STATIONS.items():
    row={'icao':'K'+sid,'iem_id':sid,'network':state+'_ASOS','season':'2009-10-01/2010-04-01 UTC','requested_hours':int((END-START).total_seconds()/3600)}
    try:
        geo=json.loads(fetch(f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'))
        hits=[x for x in geo['features'] if x['id']==sid]
        if len(hits)!=1: raise ValueError(f'metadata station matches={len(hits)}')
        p=hits[0]['properties'];row.update(archive_begin=p.get('archive_begin'),archive_end=p.get('archive_end'),attributes=json.dumps(p.get('attributes',{}),sort_keys=True),station_lon=hits[0]['geometry']['coordinates'][0],station_lat=hits[0]['geometry']['coordinates'][1],station_name=p.get('sname'))
    except Exception as e: row['metadata_error']=str(e)
    params={'station':sid,'data':'sknt,gust,peak_wind_gust','sts':START.strftime('%Y-%m-%dT%H:%MZ'),'ets':END.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','report_type':'3','format':'onlycomma','missing':'M'}
    url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
    try:
        text=fetch(url)
        raw=list(csv.DictReader(io.StringIO(text)))
        if not raw or 'valid' not in raw[0]: raise ValueError('empty/malformed CSV: '+text[:100])
        bins={};reports=0;wind=0;gust=0;peak=0
        for r in raw:
            t=datetime.strptime(r['valid'],'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            if not START<=t<END:continue
            reports+=1
            if r['sknt'] not in ('M','',None):wind+=1
            if r['gust'] not in ('M','',None):gust+=1
            if r['peak_wind_gust'] not in ('M','',None):peak+=1
            hour=t.replace(minute=0)
            if hour not in bins or (bins[hour]['sknt'] in ('M','',None) and r['sknt'] not in ('M','',None)):bins[hour]=r
        wh=sum(v['sknt'] not in ('M','',None) for v in bins.values())
        row.update(reports=reports,hours_with_routine_report=len(bins),hours_with_wind=wh,missing_wind_hour_frac=round(1-wh/row['requested_hours'],4),gust_report_count=gust,peak_wind_report_count=peak,probe_url=url)
    except Exception as e:row['probe_error']=str(e)
    rows.append(row)
    print(sid,row.get('archive_begin'),row.get('hours_with_wind'),row.get('missing_wind_hour_frac'),row.get('probe_error'),flush=True)
with (HERE/'station_probe_2009_10.csv').open('w',newline='') as f:
    cols=list(dict.fromkeys(k for row in rows for k in row))
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
print('saved',HERE/'station_probe_2009_10.csv')
