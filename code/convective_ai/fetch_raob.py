"""Fetch real nearest-sounding RAOB profiles for frozen ASOS events (IEM)."""
import csv,json,urllib.request,urllib.parse,datetime
from pathlib import Path
root=Path(__file__).parent
m={'USM00072558':'KOAX','USM00072456':'KTOP','USM00074646':'KLMN','USM00074455':'KDVN'}
records=[]
for r in csv.DictReader((root/'events.csv').open()):
    station=m[r['raob_igra_id']]
    peak=datetime.datetime.fromisoformat(r['peak_utc'].replace('Z','+00:00'))
    base=peak.replace(hour=0,minute=0,second=0,microsecond=0)
    times=[base+datetime.timedelta(hours=h) for h in (-12,0,12,24)]
    closest=min(times,key=lambda t:abs(t-peak))
    url='https://mesonet.agron.iastate.edu/json/raob.py?'+urllib.parse.urlencode({'station':station,'ts':closest.strftime('%Y-%m-%dT%H:%M:%SZ')})
    data=json.load(urllib.request.urlopen(url,timeout=45))
    profiles=data.get('profiles',[])
    records.append({'event_id':r['event_id'],'station':station,'requested_utc':closest.isoformat(),'peak_utc':r['peak_utc'],'url':url,'profiles':profiles,'levels':sum(len(p.get('profile',[])) for p in profiles)})
with (root/'raob_raw.json').open('x') as f:json.dump(records,f)
for r in records:print(r['event_id'],r['station'],r['requested_utc'],r['levels'])
