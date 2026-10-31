import csv,math,numpy as np
from earth2studio.models.px import StormCast
m=StormCast.load_model(StormCast.load_default_package())
rows=list(csv.DictReader(open('/content/events_r2_verified.csv')))
for r in rows:
 a=np.sin((np.deg2rad(m.lat)-math.radians(float(r['lat'])))/2)**2+np.cos(np.deg2rad(m.lat))*math.cos(math.radians(float(r['lat'])))*np.sin((np.deg2rad(m.lon%360)-math.radians(float(r['lon'])%360))/2)**2
 print('GRID',r['group'],r['id'],r['station'],round(float(12742*np.arcsin(np.sqrt(np.minimum(a,1))).min()),1),flush=True)
