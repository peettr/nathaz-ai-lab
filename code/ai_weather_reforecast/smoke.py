import time, torch, numpy as np
from earth2studio.models.px import Pangu6
from earth2studio.data import ARCO
s=time.time(); m=Pangu6.load_model(Pangu6.load_default_package());print('PANGU_LOADED',time.time()-s,flush=True)
s=time.time(); a=ARCO(verbose=False)([np.datetime64('2018-08-10T06:00')],['t1000']);print('ARCO_LOADED',a.shape,float(a.values.mean()),time.time()-s,flush=True)
print('INPUT',list(m.input_coords()['variable']),flush=True)
