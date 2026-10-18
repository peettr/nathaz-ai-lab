"""Radar for separately reported TS/gust cases. Index palette follows IEM n0q mapping."""
import datetime as dt,io,json,math,requests,time
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
rows=[json.loads(l) for l in open('/content/s0_metar_extra.jsonl')]
def scan(x):
 t=dt.datetime.fromisoformat(x['hit']['utc']);lat=float(x['lat']);lon=float(x['lon']);pixelx=round((lon+126)/.005);pixely=round((50-lat)/.005)
 base=t.replace(second=0,microsecond=0);base=base.replace(minute=base.minute//5*5)
 times=[base+dt.timedelta(minutes=off) for off in range(-30,36,5) if abs(((base+dt.timedelta(minutes=off))-t).total_seconds())<=1800]
 times.sort(key=lambda w:abs((w-t).total_seconds()))
 best=-999;urls=[];errors=[];first35=None;first40=None
 for when in times:
  u='https://mesonet.agron.iastate.edu/archive/data/'+when.strftime('%Y/%m/%d')+'/GIS/uscomp/n0q_'+when.strftime('%Y%m%d%H%M')+'.png'
  try:
   response=requests.get(u,timeout=45);response.raise_for_status();im=Image.open(io.BytesIO(response.content))
   dy=round(25/111/.005)+2;dx=round(25/(111*math.cos(math.radians(lat)))/.005)+2
   box=(max(0,pixelx-dx),max(0,pixely-dy),min(im.width,pixelx+dx+1),min(im.height,pixely+dy+1))
   sub=im.crop(box);vals=sub.load();vmax=-999
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
 return {**x,'radar_max_dbz':best,'radar_35':first35 is not None,'radar_40':first40 is not None,'radar_evidence_url':first40 or first35 or (urls[-1] if urls else ''),'radar_scans':len(urls),'radar_errors':errors}
with ThreadPoolExecutor(max_workers=4) as pool,open('/content/s0_radar_extra.jsonl','x') as f:
 for i,x in enumerate(pool.map(scan,rows),1):
  f.write(json.dumps(x)+'\n');f.flush()
  if i%5==0:print('RADAR_EXTRA',i,len(rows),flush=True)
