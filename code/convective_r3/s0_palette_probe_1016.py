import requests,io,numpy as np,collections
from PIL import Image
u='https://mesonet.agron.iastate.edu/archive/data/2022/05/11/GIS/uscomp/n0q_202205110535.png';r=requests.get(u,timeout=75);print('bytes',len(r.content),r.status_code)
im=Image.open(io.BytesIO(r.content));p=im.getpalette();print('mode',im.mode,'size',im.size,'idx145 rgb',p[145*3:145*3+3]);print('colors140-155',[(i,tuple(p[3*i:3*i+3])) for i in range(140,156)])
lat,lon=35.4308,-99.3943;x=round((lon+126)/.005);y=round((50-lat)/.005)
v=np.asarray(im.crop((x-65,y-55,x+65,y+55)));print('crop max',v.max(),'count>=145',(v>=145).sum(),'top',collections.Counter(v.flat).most_common(12))
