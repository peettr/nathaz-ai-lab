"""Check missing one-minute wind in ±6h around seasonal METAR combined gust/PK peak."""
import csv,io,json,urllib.parse,urllib.request,datetime as dt,os,time,traceback
from pathlib import Path
P=Path('/content/site_stage_audit');a=[json.loads(z) for z in (P/'season_audit.jsonl').read_text().splitlines()]
f=P/'metar_peak_gaps.jsonl';done=set()
if f.exists():
 for s in f.read_text().splitlines():
  try:z=json.loads(s);done.add((z['station'],z['season']))
  except:pass
for i,x in enumerate(a):
 key=x['station'],x['season']
 if key in done:continue
 g=x.get('metar_max_gust') or {};p=x.get('metar_max_pk') or {}
 selected=('pk',p) if p.get('knots',-1)>=g.get('knots',-1) else ('gust',g)
 kind,z=selected
 if not z:
  r={'station':key[0],'season':key[1],'error':'no METAR gust or PK peak'}
 else:
  t0=z.get('peak_wind_time_raw') if kind=='pk' else z.get('report_utc')
  try:
   t=dt.datetime.fromisoformat(t0.replace(' ','T').replace('Z','+00:00')).replace(tzinfo=None)
   start=t-dt.timedelta(hours=6);end=t+dt.timedelta(hours=6)
   q={'station':key[0][1:],'vars':'sknt,gust_sknt','sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':(end+dt.timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','what':'download'}
   url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?'+urllib.parse.urlencode(q)
   rows=list(csv.DictReader(io.StringIO(urllib.request.urlopen(url,timeout=100).read().decode())))
   got=set();wind=set()
   for row in rows:
    try:tt=dt.datetime.strptime(row['valid(UTC)'],'%Y-%m-%d %H:%M')
    except:continue
    k=round((tt-start).total_seconds()/60)
    if 0<=k<=720:
     got.add(k)
     if row.get('sknt') not in ('','M',None):wind.add(k)
   r={'station':key[0],'season':key[1],'metar_peak_type':kind,'metar_peak_knots':z['knots'],'metar_peak_utc':t.isoformat()+'Z','window_expected':721,'window_missing_rows':721-len(got),'window_missing_wind':721-len(wind),'source_url':url}
  except Exception as e:r={'station':key[0],'season':key[1],'error':repr(e)}
 with f.open('a') as out:out.write(json.dumps(r)+'\n');out.flush();os.fsync(out.fileno())
 if i%15==0:print('METAR_GAP',i,len(a),flush=True)
(P/'metar_gaps.exit.json').open('x').write(json.dumps({'total':sum(1 for _ in f.open()),'expected':len(a)}))
