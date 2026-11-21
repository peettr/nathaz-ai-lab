"""Write frozen event manifest from NOAA and IEM, nearest active IGRA RAOB."""
import csv,json,urllib.request,math,datetime
from pathlib import Path
ROOT=Path(__file__).parent
rows=[json.loads(s) for s in (ROOT/'observations.jsonl').read_text().splitlines() if s.startswith('{')]
url='https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt'
lines=urllib.request.urlopen(url,timeout=45).read().decode().splitlines()
stations=[]
for line in lines:
    try:
        sid=line[:11].strip();lat=float(line[12:20]);lon=float(line[21:30]);name=line[41:71].strip();last=int(line[77:81]);count=int(line[82:88])
        if sid.startswith('US') and last>=2024 and count>1000:stations.append((sid,lat,lon,name,last,count))
    except ValueError:pass

def km(a,b,c,d):
    a,c=map(math.radians,(a,c)); delta_lon=math.radians(d-b)
    t=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(delta_lon/2)**2
    return 6371*2*math.asin(math.sqrt(min(t,1)))

out=[]
for r in rows:
    lat=float(r['lat']);lon=float(r['lon']);nearest=min(stations,key=lambda s:km(lat,lon,s[1],s[2]))
    observed=max((float(y[k]),y.get('peak_wind_time') if k=='peak_wind_gust' else y['valid']) for y in r['iem_top'] for k in ('gust','peak_wind_gust') if y.get(k) not in ('M',None,''))
    assert abs(observed[0]-float(r['ncei_kt']))<1,'NCEI-IEM mismatch'
    out.append({'event_id':r['id'],'station':r['station'],'location':r['location'],'lat':lat,'lon':lon,'peak_utc':observed[1]+'Z','peak_gust_kt':observed[0],'peak_gust_ms':round(observed[0]*0.514444,3),'noaa_magnitude_kt':r['ncei_kt'],'ncei_source':r['source'],'noaa_bulk_url':r['ncei_url'],'iem_url':r['iem_url'],'raob_igra_id':nearest[0],'raob_name':nearest[3],'raob_lat':nearest[1],'raob_lon':nearest[2],'raob_distance_km':round(km(lat,lon,nearest[1],nearest[2]),1),'raob_station_list_url':url})
with (ROOT/'events.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('events',len(out),'stations',len(stations))
for x in out:print(x['event_id'],x['station'],x['peak_utc'],x['peak_gust_kt'],x['raob_igra_id'],x['raob_name'],x['raob_distance_km'])
