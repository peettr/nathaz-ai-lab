"""Recover only uncached Q5 days from NOAA annual fixed-width ISD during API outage."""
import urllib.request,gzip,re,json,hashlib,datetime
from pathlib import Path
p=Path('/content/sens2'); H=json.loads((p/'isd_station_ids.json').read_text());bad=[json.loads(x) for x in (p/'qc_station_seasons.jsonl').read_text().splitlines() if '"error"' in x]
annual=p/'annual'; annual.mkdir(exist_ok=True)
byurl={}; provenance=[]; cached={}
for x in bad:
 st,y=x['station'],x['season_year'];day=re.search(r"'([0-9]{4}-[0-9]{2}-[0-9]{2})'",x['error']).group(1);station=sorted(H[st],key=lambda z:z[1],reverse=True)[0][0];year=day[:4]
 u=f'https://www.ncei.noaa.gov/pub/data/noaa/{year}/{station[:6]}-{station[6:]}-{year}.gz'
 if u not in cached:
  b=urllib.request.urlopen(u,timeout=40).read();raw=gzip.decompress(b).decode('latin-1');cached[u]=raw
  (annual/(station+'_'+year+'.gz')).write_bytes(b)
  provenance.append({'url':u,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 rows=[]
 for rec in cached[u].splitlines():
  if rec[15:23]!=day.replace('-',''):continue
  assert len(rec)>=105 and rec[:4].isdigit() and rec[4:15]==station
  date=f'{day}T{rec[23:25]}:{rec[25:27]}:00'
  r=rec.find('REM');end=rec.find('EQD',r+3) if r>=0 else -1
  rem=rec[r+3:end if end>r else None] if r>=0 else ''
  a=rec[105:r if r>=0 else None];m=re.search(r'OC1(\d{4})(.)',a)
  rows.append({'DATE':date,'REM':rem,'OC1':m.group(1)+','+m.group(2) if m else '', 'WND':','.join((rec[60:63],rec[63],rec[64],rec[65:69],rec[69])), 'SOURCE':rec[27]})
 assert rows,(st,y,day)
 api=f'https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations={station}&startDate={day}&endDate={day}&format=json&includeAttributes=true'
 byurl[api]=json.dumps(rows).encode().decode()
 provenance.append({'station':st,'season_year':y,'date':day,'records':len(rows),'api_url':api,'annual_url':u})
(p/'fallback_isd.json').write_text(json.dumps(byurl));(p/'fallback_provenance.json').write_text(json.dumps(provenance,indent=2))
print('FALLBACK',len(byurl),'ANNUAL',len(cached), 'ROWS',sum(len(json.loads(z)) for z in byurl.values()))
# Internal validation against archived API: KJAN 2011-01-01 03:54 record.
u='https://www.ncei.noaa.gov/pub/data/noaa/2011/722350-03940-2011.gz'; r=cached[u] if u in cached else gzip.decompress(urllib.request.urlopen(u,timeout=40).read()).decode('latin-1'); z=next(t for t in r.splitlines() if t[15:27]=='201101010354');m=re.search(r'OC1(\d{4})(.)',z[105:z.find('REM')]);assert m and (m.group(1),m.group(2))==('0242','5');assert z[60:70]=='1905V00825';print('CONTROL_MATCH',m.group(1)+','+m.group(2),z[60:70])
