from pathlib import Path
import hashlib,json,tarfile
r=Path(__file__).resolve().parent
b=r/'stage_t4/FluidX3D_gate0_B/src'
def edit(name,old,new):
 p=b/name;t=p.read_text();assert t.count(old)==1,(name,old,t.count(old));p.write_text(t.replace(old,new))
edit('lbm.hpp','Memory<float> ground_force; // test-only applied wall force per cell','Memory<float> ground_force; // test-only applied wall force per cell\n\tMemory<float> ground_bounce_force; // B only: counterfactual native bounce impulse')
edit('lbm.cpp','kernel_stream_collide.add_parameters(ground_force);','ground_bounce_force = Memory<float>(device, N);\n\tkernel_stream_collide.add_parameters(ground_force, ground_bounce_force);')
edit('kernel.cpp',', global float* ground_force // test-only applied Fx diagnostic',', global float* ground_force, global float* ground_bounce_force // fixture-only impulses')
# For each unmirrored ground link compare its actual incoming population with
# the incoming population that ALL-ground mirror would supply at the same state.
# All four diagonal links are included; c(i) supplies their signed x component.
edit('kernel.cpp','\tconst bool ground_first_fluid=flat_ground_eligible(n,flags);','''\tconst bool ground_first_fluid=flat_ground_eligible(n,flags);
#ifdef WALL_GATE0
    float bounce_impulse_x=0.0f;
    if((int)ground_xyz.z+def_Oz==def_ground_first_fluid_z && (flags[j[6]]&TYPE_BO)==TYPE_S) {
        const bool m9=ground_first_fluid && flat_ground_eligible(j[2],flags);
        const bool m16=ground_first_fluid && flat_ground_eligible(j[1],flags);
        const bool m11=ground_first_fluid && flat_ground_eligible(j[4],flags);
        const bool m18=ground_first_fluid && flat_ground_eligible(j[3],flags);
        if(!m9) bounce_impulse_x+=c(9u)*(fhn[9]-load(fi,index_f(j[6],t%2ul ? 15u : 16u)));
        if(!m16) bounce_impulse_x+=c(16u)*(fhn[16]-load(fi,index_f(j[1],t%2ul ? 10u : 9u)));
        if(!m11) bounce_impulse_x+=c(11u)*(fhn[11]-load(fi,index_f(j[6],t%2ul ? 17u : 18u)));
        if(!m18) bounce_impulse_x+=c(18u)*(fhn[18]-load(fi,index_f(j[3],t%2ul ? 12u : 11u)));
    }
    ground_bounce_force[n]=bounce_impulse_x;
#endif''')
edit('setup.cpp','    evidence<<"step,mass,px,pz,wall_fx_sum\\n";','    evidence<<"step,mass,px,pz,wall_fx_sum,bounce_counterfactual_sum\\n";')
edit('setup.cpp','        double fx=0.0;','        double fx=0.0,bounce=0.0;')
edit('setup.cpp','gate.lbm_domain[0]->ground_force.read_from_device();','gate.lbm_domain[0]->ground_force.read_from_device();\n            gate.lbm_domain[0]->ground_bounce_force.read_from_device();')
edit('setup.cpp','fx+=gate.lbm_domain[0]->ground_force.x[n];','fx+=gate.lbm_domain[0]->ground_force.x[n];\n                bounce+=gate.lbm_domain[0]->ground_bounce_force.x[n];')
edit('setup.cpp','<<","<<pz<<","<<fx<<"\\n";evidence.flush();','<<","<<pz<<","<<fx<<","<<bounce<<"\\n";evidence.flush();')
m=r/'stage_t4/manifest.json';v=json.loads(m.read_text());v['fixture_B_sha256']={p:hashlib.sha256((b/p).read_bytes()).hexdigest() for p in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','lbm.hpp')};m.write_text(json.dumps(v,indent=2)+'\n')
a=r/'stage_t4_v2.tar.gz';assert not a.exists()
with tarfile.open(a,'w:gz') as f:f.add(r/'stage_t4',arcname='stage_t4')
print('bundle',a,hashlib.sha256(a.read_bytes()).hexdigest())
