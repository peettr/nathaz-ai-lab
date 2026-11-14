"""S0 radar gate: IEM n0q palette indexed dBZ at 0.005-degree resolution."""
import csv,datetime as dt,io,json,math,pathlib,time,requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
R=pathlib.Path('/content/r3_s0');rows=[json.loads(x) for x in (R/'s0_metar_checked.jsonl').open() if '"metar_pass"' in x]
out=R/'s0_radar_checked.jsonl';assert not out.exists()
# IEM documented n0q index 1=-32 dBZ, increments 0.5 dBZ; 0=no data.
def scan(x):
 t=dt.datetime.fromisoformat(x['hit']['utc']); lat=float(x['lat']);lon=float(x['lon']);
 pixelx=round((lon+126)/.005);pixely=round((50-lat)/.005)
 base=t.replace(second=0,microsecond=0);base=base.replace(minute=base.minute//5*5)
 times=[base+dt.timedelta(minutes=off) for off in range(-30,36,5) if abs(((base+dt.timedelta(minutes=off))-t).total_seconds())<=1800]
 times.sort(key=lambda w:abs((w-t).total_seconds()))
 best=-999; urls=[]; errors=[];first35=None;first40=None
 for when in times:
  u='https://mesonet.agron.iastate.edu/archive/data/'+when.strftime('%Y/%m/%d')+'/GIS/uscomp/n0q_'+when.strftime('%Y%m%d%H%M')+'.png'
  try:
   response=requests.get(u,timeout=45);response.raise_for_status();im=Image.open(io.BytesIO(response.content))
   # Bounding box with precise haversine on candidate pixels; nearby ±25km at each latitude.
   dy=round(25/111/.005)+2;dx=round(25/(111*math.cos(math.radians(lat)))/.005)+2
   box=(max(0,pixelx-dx),max(0,pixely-dy),min(im.width,pixelx+dx+1),min(im.height,pixely+dy+1))
   sub=im.crop(box); vals=sub.load();vmax=-999
   for j in range(sub.height):
    lat2=50-(box[1]+j)*.005
    for i in range(sub.width):
     lon2=-126+(box[0]+i)*.005
     a=math.sin(math.radians(lat2-lat)/2)**2+math.cos(math.radians(lat))*math.cos(math.radians(lat2))*math.sin(math.radians(lon2-lon)/2)**2
     if 12742*math.asin(min(1,math.sqrt(a)))<=25:
      val=vals[i,j]
      if val>0:vmax=max(vmax,-32+0.5*(val-1))
   best=max(best,vmax);urls.append(u)
   if vmax>=35 and not first35:first35=u
   if vmax>=40:first40=u;break
  except Exception as e:errors.append((u,repr(e)))
 return dict(**x,radar_max_dbz=best,radar_35=first35 is not None,radar_40=first40 is not None,radar_evidence_url=first40 or first35 or (urls[-1] if urls else ''),radar_scans=len(urls),radar_errors=errors)
start=time.monotonic();counts={'40':0,'35':0,'no':0,'error':0}
with ThreadPoolExecutor(max_workers=4) as pool,out.open('x') as f:
 for j,r in enumerate(pool.map(scan,rows),1):
  f.write(json.dumps(r)+'\n');f.flush()
  key='40' if r['radar_40'] else '35' if r['radar_35'] else 'error' if r['radar_errors'] else 'no';counts[key]+=1
  if j%20==0:print('RADAR_PROGRESS',j,len(rows),counts,'min',round((time.monotonic()-start)/60,2),flush=True)
print('RADAR_DONE',len(rows),counts,flush=True)
