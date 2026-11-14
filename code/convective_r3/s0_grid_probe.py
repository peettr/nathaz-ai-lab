import inspect
from earth2studio.models.px import StormCast,StormCastCONUS
for cls in (StormCast,StormCastCONUS):
 print(cls.__name__,inspect.signature(cls.load_model),inspect.getsource(cls.load_default_package),flush=True)
 try:
  m=cls.load_model(cls.load_default_package())
  print('GRID',cls.__name__,m.lat.shape,m.lon.shape,float(m.lat.min()),float(m.lat.max()),float(m.lon.min()),float(m.lon.max()),flush=True)
  import numpy as np
  np.savez_compressed('/content/'+cls.__name__+'_grid.npz',lat=m.lat,lon=m.lon)
  del m
 except Exception as e:print('ERROR',cls.__name__,repr(e),flush=True)
