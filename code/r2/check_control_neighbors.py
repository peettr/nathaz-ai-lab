"""Independent neighbor-METAR cross-check of candidate controls, no QC recovery claim."""
import csv,datetime as dt,json,math,urllib.parse,urllib.request,time
from pathlib import Path
R=Path(__file__).parent;controls=list(csv.DictReader((R/'controls_r2_candidates.csv').open()))
state_abbrev={'TEXAS':'TX','IOWA':'IA','NEBRASKA':'NE','KANSAS':'KS','OKLAHOMA':'OK','ARKANSAS':'AR'}
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ResearchLab-ConvectiveValidation/1.0'})
    with urllib.request.urlopen(req,timeout=45) as f:return f.read().decode()
def distance(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c);h=math.sin((p1-p2)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(b-d)/2)**2
    return 12742*math.asin(math.sqrt(h))
networks={}
out=[]
for e in controls:
    st=state_abbrev[e['state']];key=st+'_ASOS';rec={'id':e['id'],'station':e['station'],'time':e['utc'],'network':key,'neighbors':[],'validation':'pending'}
    try:
        if key not in networks:networks[key]=json.loads(get('https://mesonet.agron.iastate.edu/geojson/network.py?'+urllib.parse.urlencode({'network':key})))['features']
        lat,lon=float(e['lat']),float(e['lon']);near=[]
        for f in networks[key]:
            x,y=f['geometry']['coordinates'][:2];dist=distance(lat,lon,y,x)
            if 1<dist<=50:near.append((dist,f['properties'].get('sid') or f['properties'].get('id')))
        center=dt.datetime.fromisoformat(e['utc']);start=center-dt.timedelta(hours=3);end=center+dt.timedelta(hours=3)
        for dist,sid in sorted(near):
            if not sid:continue
            params={'station':sid,'sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
            url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
            text=get(url);records=list(csv.DictReader(text.splitlines()))
            gusts=[]
            for r in records:
                for field in ('gust','peak_wind_gust'):
                    try:gusts.append(float(r[field]))
                    except (KeyError,ValueError,TypeError):pass
            rec['neighbors'].append({'station':sid,'km':round(dist,2),'n_reports':len(records),'peak_kt':max(gusts) if gusts else None,'url':url})
            time.sleep(.15)
        peaks=[n['peak_kt'] for n in rec['neighbors'] if n['peak_kt'] is not None]
        rec['validation']='nearby_metar_lt40' if peaks and all(x<40 for x in peaks) else ('nearby_metar_ge40' if any(x>=40 for x in peaks) else 'no_independent_neighbor_peak')
    except Exception as ex:rec['validation']='error';rec['error']=repr(ex)
    out.append(rec);print(rec['id'],rec['validation'],len(rec['neighbors']),flush=True)
    with (R/'segment2_v1_20261014'/'control_neighbor_audit.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
