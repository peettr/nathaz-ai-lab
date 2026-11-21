#!/usr/bin/env python3
"""CPU mirror of T15 algebra, not a GPU E3 substitute."""
import math, json, pathlib
R=pathlib.Path(__file__).resolve().parent
rho=1.13
ux,uy=0.14,0.03
z0=0.024
kappa=0.4
um=math.hypot(ux,uy)
tau_w=rho*(kappa*um/math.log((1.5+z0)/z0))**2
epsilon=um/10
old=(0.0001, -0.00002)
tau_f=((1-epsilon)*old[0]+epsilon*tau_w*ux/um,(1-epsilon)*old[1]+epsilon*tau_w*uy/um)
area=1.0
volume=1.0
force_density=(-tau_f[0]*area/volume,-tau_f[1]*area/volume)
applied_force=(force_density[0]*volume,force_density[1]*volume)
expected=(-tau_f[0]*area,-tau_f[1]*area)
rel=math.hypot(*(a-b for a,b in zip(applied_force,expected)))/math.hypot(*expected)
assert rel<=1e-6
(R/'E3_ALGEBRA_FIXTURE.json').write_text(json.dumps({'status':'CPU_ALGEBRA_ONLY_NOT_GPU_E3','rho':rho,'u':[ux,uy],'epsilon':epsilon,'tau_w':tau_w,'tau_f_xy':tau_f,'area':area,'force_xy':applied_force,'relative_error':rel},indent=2)+'\n')
print('CPU_ALGEBRA_PASS',rel,'GPU_E3_NOT_TESTED')
