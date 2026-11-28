import sys,pathlib,warnings,traceback,inspect
base=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/envcheck_v1');sys.path.insert(0,str(base))
import envcheck_gc37x_v1b as m
import numpy as np
import metpy.calc as c
p=m.ROOT/'drivers_N1_v1/GFS/2024061418/FILE:2024-06-14_18'
idx=m.mask_points(p,38.06,-97.86); slabs,_=m.records(p,idx)
values={f:np.stack([slabs[f,100*lev] for lev in m.LEVELS]) for f in m.FIELDS}
for j in range(len(idx)):
    with warnings.catch_warnings():
        warnings.filterwarnings('error',message='Interpolation point out of data bounds')
        try: m.profile(np.array(m.LEVELS,dtype=float),values['GHT'][:,j],values['TT'][:,j],values['SPECHUMD'][:,j],values['UU'][:,j],values['VV'][:,j],slabs['SOILHGT',200100][j])
        except UserWarning:
            print('WARNING_COLUMN',j,'grid_index',idx[j]);traceback.print_exc();break
else:print('NO_WARNING')
for name in ('storm_relative_helicity','bunkers_storm_motion','bulk_shear'):
    src=inspect.getsource(getattr(c,name))
    print('SOURCE',name, '\n'.join(line for line in src.splitlines() if any(term in line for term in ('get_layer','bottom','interpolate','height[','depth','mean_pressure_weighted'))))
