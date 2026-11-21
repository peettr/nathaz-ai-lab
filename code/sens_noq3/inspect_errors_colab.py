import json,tarfile,gzip,csv,io
from pathlib import Path
p=Path('/content/sens2'); q=[json.loads(x) for x in (p/'qc_station_seasons.jsonl').read_text().splitlines() if '"error"' in x]
print('ERRORS',[(x['station'],x['season_year'],x['error']) for x in q]);
with tarfile.open(p/'source_stage.tar') as t:
 for x in q:
  st,y=x['station'],x['season_year']; raw=gzip.decompress(t.extractfile('iem/%s_%s.gz'%(st,y)).read()).decode('utf-8','replace'); rs=list(csv.DictReader(io.StringIO(raw)))
  cs=sorted([(float(z[k]),k,z['valid'],z.get('metar','')[:150]) for z in rs for k in ('gust','peak_wind_gust') if z.get(k) not in ('','M',None) and z[k].replace('.','',1).isdigit()],reverse=True)
  print('TOP',st,y,cs[:3])
