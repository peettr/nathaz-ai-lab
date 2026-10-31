import urllib.request,gzip,json,re
from pathlib import Path
p=Path('/content/sens2');H=json.loads((p/'isd_station_ids.json').read_text());e=[json.loads(x) for x in (p/'qc_station_seasons.jsonl').read_text().splitlines() if '"error"' in x]
for x in e:
 st,y=x['station'],x['season_year'];d=re.search(r"'([0-9]{4}-[0-9]{2}-[0-9]{2})'",x['error']).group(1);id=sorted(H[st],key=lambda z:z[1],reverse=True)[0][0];u=f'https://www.ncei.noaa.gov/pub/data/noaa/{d[:4]}/{id[:6]}-{id[6:]}-{d[:4]}.gz'
 try:
  z=urllib.request.urlopen(u,timeout=25);raw=gzip.decompress(z.read()).decode('latin-1');print('OK',st,y,d,id,len(raw),len([a for a in raw.splitlines() if a[15:23]==d.replace('-','')]))
 except Exception as ex:print('ERR',st,y,d,id,repr(ex),u)
