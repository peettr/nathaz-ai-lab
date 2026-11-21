from pathlib import Path
import numpy as np,json
p=Path('/content/l264a100/texas');a=np.load(p/'noaa_lat.npy');b=np.load(p/'noaa_lon.npy');h,w=440,408
for target in ((29.,-94.),(29.,-93.),(29.,-96.)):
 yy,xx=np.unravel_index(np.argmin((a-target[0])**2+(((b-target[1]+180)%360)-180)**2),a.shape)
 y=max(0,min(a.shape[0]-h,yy-h//2));x=max(0,min(a.shape[1]-w,xx-w//2)); corners=[(float(a[i,j]),float((b[i,j]+180)%360-180)) for i,j in ((y,x),(y,x+w-1),(y+h-1,x),(y+h-1,x+w-1))]
 overlap=max(0,min(y+h,692)-max(y,252))*max(0,min(x+w,969)-max(x,561))
 print('target',target,'offset',(y,x),'corners',corners,'west_overlap',overlap/(h*w),flush=True)
