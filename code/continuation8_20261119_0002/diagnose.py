#!/usr/bin/env python3
"""Read-only reconstruction of T15 E3' periodic fixture ground eligibility."""
import csv, gzip, json, math, pathlib, hashlib
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent
P7=ROOT/'continuation7_20261118_231514'
P2=ROOT/'continuation2_20261118_165345'
EV=P7/'session_luw-t15-a100-19309021/evidence/E3_native_evolution.csv.gz'
NATIVE=P7/'session_luw-t15-a100-19309021/evidence/E3_native_native_e3.csv.gz'
LOG=P2/'session_luw-t15-a100-adacd84b/evidence/WM_s108_solver.log'
KERNEL=P7/'stage/FluidX3D_e3/src/kernel.cpp'
SETUP=P7/'stage/FluidX3D_e3/src/setup.cpp'
for f in (EV,NATIVE,LOG,KERNEL,SETUP): assert f.is_file(),f
code=KERNEL.read_text()
assert 'xyz.x<=1u || xyz.x+2u>=def_Nx' in code and 'xyz.y<=1u || xyz.y+2u>=def_Ny' in code
src=SETUP.read_text()
assert 'LBM gate(24u,24u,12u,0.02f,0.000001f)' in src
assert 'if(z==0u) gate.flags[n]=TYPE_S' in src
assert 'if(z==gate.get_Nz()-1u) gate.flags[n]=TYPE_E' in src
assert 'const uint sites[8]={2u,5u,8u,11u,14u,17u,19u,21u};' in src

def map_ground(nx,ny):
    return [[int(1<x<nx-2 and 1<y<ny-2) for x in range(nx)] for y in range(ny)]
small=map_ground(24,24); yes=sum(map(sum,small)); no=24*24-yes
assert (yes,no)==(400,176)
with (HERE/'E3_eligibility_map.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['y']+[str(i) for i in range(24)])
    for y,row in enumerate(small):w.writerow([y]+row)
with gzip.open(EV,'rt') as f:
    reader=csv.DictReader(f); first=next(reader); second=next(reader)
with gzip.open(NATIVE,'rt') as f:
    reader=csv.DictReader(f);record=next(reader)
assert int(record['step'])==0
mean0=float(first['mean_match_speed']);mean1=float(second['mean_match_speed'])
initial=float(record['match_speed_lattice'])
nu=.02;F=1e-6;H=10.;z0=.024;ustar=math.sqrt(F*H)
firstU=ustar/.4*math.log((.5+z0)/z0)
tau_noslip=nu*firstU/.5
tau_fraction=tau_noslip*no/(24*24)
prod=map_ground(550,100);prod_yes=sum(map(sum,prod)); prod_no=550*100-prod_yes
log=LOG.read_text(errors='replace')
assert 'measured=52177 expected_interior=52416' in log
# This is a geometry-only mask; the measured count includes native flags and neighbor requirements.
data={'source_sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (EV,NATIVE,LOG,KERNEL,SETUP)},'small':{'nx':24,'ny':24,'eligible_geometry_only':yes,'excluded_geometry_only':no,'excluded_fraction':no/(24*24),'ring_rows':{'y0_1_and_22_23':'all excluded','y2_through_21':'x0_1_and_22_23 excluded'},'record_sites_all_interior':True},'momentum_order':{'body_force_F':F,'fluid_height_H':H,'forcing_stress_FH':F*H,'initial_U_z0p5_loglaw':firstU,'initial_U_z1p5_record':initial,'nu':nu,'native_bounce_shear_proxy_nu_U_over_halfcell':tau_noslip,'excluded_area_averaged_drag_proxy':tau_fraction,'drag_proxy_over_forcing':tau_fraction/(F*H),'mean_match_speed_step1':mean0,'mean_match_speed_step2':mean1,'step2_minus_step1':mean1-mean0,'top_macro_gradient_proxy_only':'zero per prior top_shear.csv; distribution momentum flux unmeasured','scope':'order estimate, not measured momentum closure'},'production':{'nx':550,'ny':100,'geometry_interior':prod_yes,'geometry_excluded':prod_no,'geometry_excluded_fraction':prod_no/55000,'native_measured_eligible':52177,'native_total_minus_measured':55000-52177,'native_excluded_fraction':(55000-52177)/55000,'additional_beyond_ring':prod_yes-52177,'positions':'x=0,1,548,549 or y=0,1,98,99; 239 additional columns lack per-column native flags, spatial attribution unknown'},'assessment':'Geometry-mask and drag/drive order strongly support edge no-slip hypothesis; actual bounce stress and top distribution flux were not directly measured, so causality remains provisional.'}
(HERE/'DIAGNOSIS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in data.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
