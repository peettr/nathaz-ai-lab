import requests,io,numpy as np,collections
from PIL import Image
lat,lon=35.4308,-99.3943;timestamp='2022-05-11T05:35:00Z'; dx=.32;dy=.25;box=[lon-dx,lat-dy,lon+dx,lat+dy]
u='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q-t.cgi'
p={'service':'WMS','version':'1.1.1','request':'GetMap','layers':'nexrad-n0q-wmst','styles':'','srs':'EPSG:4326','bbox':','.join(map(str,box)),'width':128,'height':100,'format':'image/png','transparent':'true','time':timestamp}
r=requests.get(u,params=p,timeout=50);print(r.url,r.status_code,len(r.content),r.headers.get('Content-Type'),r.text[:100] if 'xml' in r.headers.get('Content-Type','') else '')
if 'image' in r.headers.get('Content-Type',''):
 im=Image.open(io.BytesIO(r.content));print(im.mode,im.size);v=np.asarray(im);print(v.shape,'uniques',collections.Counter(map(tuple,v.reshape(-1,v.shape[-1]))).most_common(12) if v.ndim==3 else collections.Counter(v.flat).most_common(12));print('palette',im.getpalette()[:30] if im.getpalette() else None)
