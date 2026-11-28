#!/usr/bin/env python3
"""Fail-closed native fixture analysis; numeric outputs only from retrieved CSV."""
import csv,json,math,pathlib
p=pathlib.Path(__file__).resolve().parent
r=list(csv.DictReader((p/'wall_gate0.csv').open()))
assert len(r)==2001 and [int(x['step']) for x in r]==list(range(2001))
v=lambda k:[float(x[k]) for x in r]
d=v('ddf_mass_offset_all_cells');rho=v('rho_mass'); px=v('px'); fx=v('wall_fx_sum')
assert all(math.isfinite(x) for x in d+rho+px+fx)
mass_rel=max(abs(x-d[0])/abs(d[0]) for x in d)
trend=math.fsum((i-1000)*y for i,y in enumerate(rho))/math.fsum((i-1000)**2 for i in range(2001))
initial20=(px[20]-px[0])-sum(fx[1:21]); tolerance=1e-4*abs(px[0]); all_px=(px[-1]-px[0])-sum(fx[1:]);
result={'ddf_initial':d[0],'ddf_max_rel_2000':mass_rel,'ddf_pass':mass_rel<=1e-6,'rho_initial':rho[0],'rho_final':rho[-1],'rho_min':min(rho),'rho_max':max(rho),'rho_linear_slope_per_step':trend,'px0':px[0],'px20_residual_ground_only':initial20,'px2000_residual_ground_only':all_px,'px_tolerance':tolerance,'eligible_first_step':int(r[1]['eligible'])}
q=p/'wall_gate0_pulse.csv'
if q.exists():
    pulses=list(csv.DictReader(q.open()));assert len(pulses)==2 and [int(x['parity']) for x in pulses]==[0,1]
    result['pulses']=[{'parity':int(x['parity']),'incoming_delta':float(x['perturbed_target'])-float(x['base_target']),'injected_delta':float(x['perturbed_slot'])-float(x['base_slot']),'ddf_delta_before':float(x['perturbed_ddf_before'])-float(x['base_ddf_before']),'ddf_delta_after':float(x['perturbed_ddf_after'])-float(x['base_ddf_after']),'target':(int(x['target_x']),int(x['target_y']),int(x['target_z']),int(x['target_dir']))} for x in pulses]
    result['pulse_pass']=all(abs(x['incoming_delta']-x['injected_delta'])<=1e-6 and abs(x['ddf_delta_after']-x['ddf_delta_before'])<=1e-6 for x in result['pulses'])
(p/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
