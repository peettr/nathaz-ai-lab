"""Diagnostic only: verify minute peaks strongly discordant with seasonal METAR.
No automatic value deletion or replacement; 20-kn screen is an explicit hypothesis.
"""
import json,csv,urllib.parse,urllib.request,datetime as dt,statistics,time,io
from pathlib import Path
p=Path('/content/site_stage_audit');a=[json.loads(z) for z in (p/'season_audit.jsonl').read_text().splitlines()]
out=[]
for x in a:
 v=x.get('minute_peak_knots');met=max((x.get('metar_max_pk') or {}).get('knots') or 0,(x.get('metar_max_gust') or {}).get('knots') or 0)
 if v is None or v-met<20:continue
 t=dt.datetime.fromisoformat(x['minute_peak_utc'].replace('Z','+00:00'))
 pars={'station':x['station'][1:],'vars':'sknt,gust_sknt','sts':(t-dt.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(t+dt.timedelta(minutes=6)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','what':'download'}
 url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?'+urllib.parse.urlencode(pars)
 try:
  rows=list(csv.DictReader(io.StringIO(urllib.request.urlopen(url,timeout=60).read().decode())))
  neighbors=[float(r['gust_sknt']) for r in rows if r['valid(UTC)']!=t.strftime('%Y-%m-%d %H:%M') and r['gust_sknt'] not in ('M','')]
  out.append({'station':x['station'],'season':x['season'],'peak_utc':x['minute_peak_utc'],'peak_knots':v,'metar_season_max_knots':met,'neighbors_10min':len(neighbors),'neighbor_median_knots':statistics.median(neighbors) if neighbors else None,'neighbor_max_knots':max(neighbors) if neighbors else None,'isolated_30kn_jump':bool(neighbors and v-max(neighbors)>=30),'raw_rows':rows,'source_url':url})
 except Exception as e:out.append({'station':x['station'],'season':x['season'],'error':repr(e),'source_url':url})
 time.sleep(.15)
(p/'peak_qc_screen.json').open('x').write(json.dumps({'screen':'minute seasonal peak minus METAR seasonal max >=20 knots; diagnostic not deletion rule','cases':out}))
print('QC',len(out),'isolated',sum(z.get('isolated_30kn_jump',False) for z in out),flush=True)
