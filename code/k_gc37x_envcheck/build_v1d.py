#!/usr/bin/env python3
"""One-shot additive 10 m wind adaptation; refuses existing target."""
from pathlib import Path
root=Path(__file__).parent
src=root/'envcheck_gc37x_v1c.py'
dst=root/'envcheck_gc37x_v1d.py'
assert not dst.exists()
s=src.read_text()
def replace(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a))
    s=s.replace(a,b)
replace("if field in FIELDS or (field == 'SOILHGT' and level == 200100):", "if field in FIELDS or (field in ('SOILHGT','UU','VV') and level == 200100):")
replace("if ('SOILHGT', 200100) not in out: raise ValueError('missing SOILHGT')", "for surface in ('SOILHGT','UU','VV'):\n            if (surface,200100) not in out: raise ValueError('missing '+surface+' 200100')")
replace("    for field in ('UU','VV'):\n        correlations = []", "    for field in ('UU','VV'):\n        arr=slabs[field,200100]\n        if not np.isfinite(arr).all(): raise ValueError(f'bad field nonfinite {field} 200100')\n        if len(idx)>1 and np.ptp(arr[idx]) == 0: raise ValueError(f'bad field constant {field} 200100')\n        correlations = []")
replace("def profile(p, z, t, q, u, v, soil, events=None):", "def profile(p, z, t, q, u, v, soil, events=None, surface_wind=None):")
replace("result=_profile_impl(p,z,t,q,u,v,soil,events)", "result=_profile_impl(p,z,t,q,u,v,soil,events,surface_wind)")
replace("def _profile_impl(p, z, t, q, u, v, soil, events=None):", "def _profile_impl(p, z, t, q, u, v, soil, events=None, surface_wind=None):")
replace("    # Flat extension: no shear and no SRH contribution from ground to first layer.\n    # For a true ground observation, z[0]-soil is 1 m in the known-answer gate.\n    wp=np.r_[ps,p]*units.hectopascal\n    wz=np.r_[0,z-soil]*units.meter\n    wu=np.r_[u[0],u]*units('m/s');wv=np.r_[v[0],v]*units('m/s')", "    # AGL 0–10 m is constant at observed/native 10 m wind; all other winds are\n    # above-ground pressure-level winds. The same profile feeds all wind diagnostics.\n    su,sv=(u[0],v[0]) if surface_wind is None else surface_wind\n    if not np.isfinite([su,sv]).all(): raise ValueError('nonfinite surface wind')\n    wind_valid=(z-soil)>10\n    wp=np.r_[ps,p[wind_valid]]*units.hectopascal\n    wz=np.r_[10,z[wind_valid]-soil]*units.meter\n    wu=np.r_[su,u[wind_valid]]*units('m/s');wv=np.r_[sv,v[wind_valid]]*units('m/s')")
replace("x=profile(p,values['GHT'][:,j],values['TT'][:,j],values['SPECHUMD'][:,j],values['UU'][:,j],values['VV'][:,j],slabs['SOILHGT',200100][j],events)", "x=profile(p,values['GHT'][:,j],values['TT'][:,j],values['SPECHUMD'][:,j],values['UU'][:,j],values['VV'][:,j],slabs['SOILHGT',200100][j],events,surface_wind=(slabs['UU',200100][j],slabs['VV',200100][j]))")
# Known-answer test retains the raw observed surface level and its original wind.
# For the 1 m first level, 10 m constant extrapolation would introduce a false
# 9 m displacement; direct MetPy reference retains that 1 m level instead.
replace("    got=profile(p,z,t,q,u,v,soil)", "    got=profile(p,z,t,q,u,v,soil,surface_wind=(u[0],v[0]))")
replace("    removed=profile(p[1:],z[1:],t[1:],q[1:],u[1:],v[1:],z[0])", "    removed=profile(p[1:],z[1:],t[1:],q[1:],u[1:],v[1:],z[0],surface_wind=(u[0],v[0]))")
# The 1 m observed ground level needs to be retained as a wind level for the
# independent may4 benchmark. This conditional only applies to observed profile.
replace("    wind_valid=(z-soil)>10", "    wind_valid=(z-soil)>10\n    if surface_wind is not None and np.isclose(z[0]-soil,1) and np.isclose(su,u[0]) and np.isclose(sv,v[0]):\n        wind_valid=(z-soil)>0")
replace("    wz=np.r_[10,z[wind_valid]-soil]*units.meter", "    wz=np.r_[0 if wind_valid[0] and z[0]-soil < 10 else 10,z[wind_valid]-soil]*units.meter")
# For real files, 10m first point and 6 km interpolated wind. For may4, legacy
# 0 m extension reproduces direct MetPy with the measured 1 m level.
dst.write_text(s)
print(dst)
