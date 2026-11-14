#!/usr/bin/env python3
"""Retry metadata timeouts only (no GRIB download); persist new audit."""
from pathlib import Path
import json,urllib.request,urllib.error,datetime,re
r=Path(__file__).resolve().parent
src=json.loads((r/'PGRB2B_ARCHIVE_PROBE_20261112.json').read_text())
rows=[]
for row in src['rows']:
 if row['dds_status']==200 and row.get('coordinates',{}).get('isobaric2',{}).get('status')==200: continue
 root=row['dds_url'].removesuffix('.dds')
 result={'cycle':row['time'],'original_dds_status':row['dds_status'],'urls':[]}
 for suffix in ('.dds','.ascii?isobaric1','.ascii?isobaric2','.ascii?isobaric3'):
  url=root+suffix
  try:
   with urllib.request.urlopen(url,timeout=50) as resp: body=resp.read(180000).decode(errors='replace'); status=resp.status
   entry={'url':url,'status':status}
   if '.ascii' in suffix: entry['levels_pa']=[float(x) for x in re.findall(r'(?<![\w])\d+\.\d+(?![\w])',body.split('---------------------------------------------')[-1])]
   if suffix=='.dds': entry['field_dimensions']={k:re.search(re.escape(k)+r'\[time = 1\]\[(isobaric\d*) = (\d+)\]',body).groups() if re.search(re.escape(k)+r'\[time = 1\]\[(isobaric\d*) = (\d+)\]',body) else None for k in ('Geopotential_height_isobaric','Temperature_isobaric','u-component_of_wind_isobaric','v-component_of_wind_isobaric','Relative_humidity_isobaric','Specific_humidity_isobaric','Vertical_velocity_pressure_isobaric')}
  except urllib.error.HTTPError as exc: entry={'url':url,'status':exc.code}
  except Exception as exc: entry={'url':url,'status':None,'error':str(exc)}
  result['urls'].append(entry)
 rows.append(result)
out={'checked_at_est':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).isoformat(),'rows':rows}
p=r/'PGRB2B_METADATA_RETRY_20261112.json'; p.write_text(json.dumps(out,indent=2)+'\n'); print(p)
for item in rows: print(item['cycle'],[(u['status'],u['url'].split('.')[-1]) for u in item['urls']])
