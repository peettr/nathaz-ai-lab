import requests,pathlib,csv,io,collections,datetime
root=pathlib.Path('/content/L26_18')
for ii,(start,end) in enumerate([('2022-09-27T08:33:48Z','2022-09-27T14:33:48Z'),('2022-09-27T20:27:35Z','2022-09-28T02:27:35Z')]):
 url='https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv'
 q='flight_id,time,latitude,longitude,SWS,FLAG,NGC,RALT&time>='+start+'&time<='+end+'&latitude>=20&latitude<=27&longitude>=-86&longitude<=-80'
 try:
  z=requests.get(url+'?'+requests.utils.requote_uri(q),timeout=180);print('FETCH',ii,z.status_code,len(z.content),z.text[:160],flush=True);z.raise_for_status()
  p=root/f'sfmr_ian_{ii}.csv';p.write_bytes(z.content)
  rows=list(csv.DictReader(io.StringIO(z.text))); print('ROWS',ii,len(rows),'FLIGHTS',collections.Counter(a['flight_id'] for a in rows[1:]),flush=True)
  for flight in set(a['flight_id'] for a in rows[1:]):
   rr=[a for a in rows[1:] if a['flight_id']==flight and a['FLAG']=='0' and a['SWS'] and float(a['SWS'])>=0]
   if not rr:continue
   print('FLIGHT',flight,'n',len(rr),'range',rr[0]['time'],rr[-1]['time'],'lat',min(float(x['latitude']) for x in rr),max(float(x['latitude']) for x in rr),'lon',min(float(x['longitude']) for x in rr),max(float(x['longitude']) for x in rr),'lowest',[(a['time'],a['latitude'],a['longitude'],a['SWS']) for a in sorted(rr,key=lambda x:float(x['SWS']))[:8]],flush=True)
 except Exception as e:print('ERROR',ii,repr(e),flush=True)
