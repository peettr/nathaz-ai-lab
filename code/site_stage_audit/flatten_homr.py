"""Flatten official HOMR station history without inferring sensor manufacturers."""
import json,csv
from pathlib import Path
p=Path(__file__).resolve().parent
h=json.load((p/'homr_history.json').open())['rows'];co={x['station']:x for x in json.load((p/'homr_station_counties.json').open())}
rows=[]
for x in h:
 st=x['station']
 if x['ncdc_id']!=co.get(st,{}).get('ncdc_id'):continue
 w=json.loads(x['wind_elements']);loc=json.loads(x['locations_2000_plus']);rel=json.loads(x['relocations'])
 for z in w:
  rows.append({'station':st,'homr_ncdc_id':x['ncdc_id'],'record':'wind_equipment','begin':z.get('date',{}).get('beginDate'),'end':z.get('date',{}).get('endDate'),'value':z.get('equipment',{}).get('equipment'),'notes':z.get('frequency'),'source_url':x['api_url']})
 for z in loc:
  rows.append({'station':st,'homr_ncdc_id':x['ncdc_id'],'record':'coordinate','begin':z.get('date',{}).get('beginDate'),'end':z.get('date',{}).get('endDate'),'value':str(z.get('latitude_dec'))+','+str(z.get('longitude_dec')),'notes':z.get('source'),'source_url':x['api_url']})
 for z in rel:
  rows.append({'station':st,'homr_ncdc_id':x['ncdc_id'],'record':'relocation','begin':z.get('date'),'end':'','value':z.get('relocation'),'notes':'HOMR station-level relocation; not necessarily wind sensor relocation','source_url':x['api_url']})
f=p/'homr_breakpoints.csv'
with f.open('x',newline='') as g:
 wr=csv.DictWriter(g,fieldnames=['station','homr_ncdc_id','record','begin','end','value','notes','source_url']);wr.writeheader();wr.writerows(rows)
print(len(rows),len(set(z['station'] for z in rows)))
