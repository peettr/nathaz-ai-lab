#!/usr/bin/env python3
"""Audit hourly station-event candidates against NWS ASOS equipment inventory.
No forecast/observation pairing. Inventory is a 2025 snapshot, not full history.
"""
import csv, io, re, urllib.request, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict,Counter
P=Path(__file__).resolve().parent
SRC=P.parent/'v2b/hourly_pool_150km.csv'
URL='https://www.weather.gov/media/asos/ASOS%20Sites%20by%20Equipment%20As%20Of%203_18_2025.xlsx'
X='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
with urllib.request.urlopen(URL,timeout=90) as r: raw=r.read()
z=zipfile.ZipFile(io.BytesIO(raw));strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(X+'si')]
def rows(sheet):
 root=ET.fromstring(z.read(f'xl/worksheets/sheet{sheet}.xml'))
 for row in root.findall('.//'+X+'sheetData/'+X+'row'):
  result={}
  for cell in row.findall(X+'c'):
   v=cell.find(X+'v');ref=re.match('[A-Z]+',cell.attrib['r']).group()
   if v is not None:result[ref]=strings[int(v.text)] if cell.attrib.get('t')=='s' else v.text
  yield result
heights={r.get('C',''):r.get('F','') for r in list(rows(13))[1:] if r.get('C')}
legacy={r.get('C',''):r.get('G','') for r in list(rows(6))[1:] if r.get('C')}
valid=list(csv.DictReader(SRC.open()));out=[]
for r in valid:
 if r['hourly_75pct']!='True' or r['event']=='ISAIAS':continue
 sid=r['station'];h=heights.get(sid,'');date=legacy.get(sid,'')
 # Inventory 2025: membership confirms site in network in 2025 but not historical status.
 try: height_m=round(float(h)*.3048,3)
 except (ValueError,TypeError):height_m=None
 # Date is Excel serial; 1899-12-30 epoch.
 try:
  import datetime
  commission=(datetime.datetime(1899,12,30)+datetime.timedelta(days=float(date))).date().isoformat()
 except (ValueError,TypeError): commission=''
 status='2025_ASOS_height_known' if height_m is not None else ('2025_ASOS_height_missing' if sid in legacy else 'not_in_2025_NWS_ASOS_inventory')
 # Conservative: historical station and actual height cannot be confirmed by 2025 snapshot alone.
 out.append(dict(event=r['event'],year=r['year'],station=sid,valid_hour_bins=r['valid_hour_bins'],distance_km=r['distance_km'],inventory_status=status,inventory_height_ft=h,inventory_height_m=height_m or '',legacy_commission=commission,historical_height_verified='no',eligible_confirmed='no',conditional_2025_snapshot='yes' if status=='2025_ASOS_height_known' and commission and commission[:4]<=r['year'] and 8<=height_m<=12 else 'no',inventory_url=URL))
with (P/'station_audit_170.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,out[0].keys());w.writeheader();w.writerows(out)
c=defaultdict(list)
for r in out:c[r['event']].append(r)
with (P/'event_qc_counts.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['event','candidate_hourly','2025_ASOS_height_known','conditional_prelim_8_12m_preexisting','historically_confirmed','at_least_3_confirmed'])
 for event,rr in c.items():w.writerow([event,len(rr),sum(x['inventory_status']=='2025_ASOS_height_known' for x in rr),sum(x['conditional_2025_snapshot']=='yes' for x in rr),0,'no'])
print('NWS xlsx bytes',len(raw),'candidate',len(out),'unique stations',len(set(r['station'] for r in out)))
print('statuses',Counter(r['inventory_status'] for r in out))
print('conditional 2025 eligible',sum(r['conditional_2025_snapshot']=='yes' for r in out),'events>=3',sum(sum(r['conditional_2025_snapshot']=='yes' for r in rr)>=3 for rr in c.values()))
print('per event',[(e,len(rr),sum(r['conditional_2025_snapshot']=='yes' for r in rr)) for e,rr in c.items()])
