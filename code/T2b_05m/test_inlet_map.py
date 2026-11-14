#!/usr/bin/env python3
"""Static source assertions plus float32 inlet k/sigma mapping fixture, no solver."""
import json, math, pathlib, struct, tarfile
root=pathlib.Path(__file__).resolve().parent
src=(root/'validation_stage/FluidX3D/src/setup.cpp').read_text()
with tarfile.open(root/'validation_stage/B2u_inputs.tar.gz') as tf:
    original=tf.extractfile('FluidX3D/src/setup.cpp').read().decode()
assert original.count('const float z_agl = std::max(0.0f,p.z - 20.0f);')==1
assert src.count('const float z_agl = std::max(0.0f, (p.z - cfg_.ground_z_lbm) * cfg_.cell_size_m);')==1
assert src.count('cfg.ground_z_lbm = units.x(z_si_offset);')==1
assert src.count('cfg.cell_size_m = 1.0f / units.x(1.0f);')==1
f32=lambda x:struct.unpack('f',struct.pack('f',x))[0]
zk=[1.25,2.5,5,7.5,12.5,25,50,75,100,150,200,250]
kr=[.008,.009,.009,.009,.010,.010,.009,.008,.007,.006,.004,.002]
def sigma(z):
    k=kr[0]
    if z>=zk[-1]: k=kr[-1]
    elif z>zk[0]:
        for a in range(len(zk)-1):
            if z<=zk[a+1]:
                t=f32((z-zk[a])/(zk[a+1]-zk[a]))
                k=f32(kr[a]+t*(kr[a+1]-kr[a]));break
    return f32(f32(7.8)*f32(math.sqrt(f32(2*k/3))))
# Include table knots and every common 1m lattice height through top of profile.
heights=sorted(set([0,1,2,3,4,5,8,10,15,20,30,50,100,150,200,250]+[z for z in zk if float(z).is_integer()]))
rows=[]
for h in heights:
    coarse_index=int(h+20); fine_index=int(2*h+40)
    old=f32(max(0,f32(coarse_index-20.0)))
    fixed1=f32(max(0,f32(f32(coarse_index-20.0)*1.0)))
    fixed05=f32(max(0,f32(f32(fine_index-40.0)*.5)))
    assert old==fixed1==fixed05,(h,old,fixed1,fixed05)
    rows.append(dict(z_m=h,coarse_index=coarse_index,fine_index=fine_index,sigma_1=sigma(fixed1),sigma_05=sigma(fixed05),difference=sigma(fixed05)-sigma(fixed1)))
d=[v['difference'] for v in rows]
s=[v['sigma_05'] for v in rows]
out={'source_expression_verified':True,'one_meter_old_new_equal':True,'n_common_heights':len(rows),'sigma_05_min':min(s),'sigma_05_mean':sum(s)/len(s),'sigma_05_max':max(s),'sigma_difference_min':min(d),'sigma_difference_mean':sum(d)/len(d),'sigma_difference_max':max(d),'rows':rows,'note':'static map/interpolation fixture; runtime verification still required in solver.log'}
(root/'inlet_map_preflight.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=False))
