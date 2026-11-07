import csv,datetime as dt,time,numpy as np,math
from earth2studio.data import HRRR,HRRR_FX
from earth2studio.lexicon.hrrr import HRRRFXLexicon
r=list(csv.DictReader(open('/content/events_r2_verified.csv')));e=[x for x in r if x['group']=='v1'][0]
peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2)
lat,lon=HRRR.grid();a=np.sin((np.deg2rad(lat)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lon)-math.radians(float(e['lon'])))/2)**2;yy,xx=np.where(12742*np.arcsin(np.sqrt(np.minimum(a,1)))<=25)
print('PILOT',init,len(yy),'GPU?',flush=True)
fx=HRRR_FX(verbose=False);levels=range(1,51)
vars=['u10m','v10m','fg10m']+[f'{v}{k}hl' for v in ('u','v','t','q','Z','p') for k in levels]
assert all(HRRRFXLexicon.VOCAB[k].startswith('wrfnat::') for k in vars if k.endswith('hl'))
t=time.monotonic()
for h in [1]:
 for block in [vars[:3]]+[ [f'{v}{k}hl' for k in levels] for v in ('u','v','t','q','Z','p')]:
  s=time.monotonic();out=fx([init],[dt.timedelta(hours=h)],block);values=out.values[0,0,:,yy,xx];print('BLOCK',block[0],len(block),values.shape,'wall',round(time.monotonic()-s,1),'range',float(np.nanmin(values)),float(np.nanmax(values)),flush=True);del out,values
print('PILOT_DONE',round(time.monotonic()-t,1),flush=True)
