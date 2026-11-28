#!/usr/bin/env python3
"""Create immutable T3c inputs from archived T3b source, without GPU compute."""
from pathlib import Path
import shutil,struct,json,hashlib,tarfile,re
R=Path(__file__).resolve().parent
OLD=R.parent/'T3b_r2'
S=R/'stage_fixed'
assert not S.exists(), 'T3c staging already exists; never overwrite'
shutil.copytree(OLD/'stage_fixed',S,symlinks=True)
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert H(S/'FluidX3D/src/setup.cpp')=='81c1b21c97882fb51c6c01c0cbec9facbe15660e4d21872d11a009fe33d57eb5'
p=S/'flatground.stl';data=bytearray(p.read_bytes());n=struct.unpack_from('<I',data,80)[0];assert n==12 and len(data)==84+50*n
coords=[[],[],[]]
for i in range(n):
 for j in range(3):
  at=84+i*50+12+12*j
  v=list(struct.unpack_from('<3f',data,at));assert v[0] in (0,350) and v[1] in (0,100) and v[2] in (-20,0)
  if v[0]==350:v[0]=550
  struct.pack_into('<3f',data,at,*v)
  for ax in range(3):coords[ax].append(v[ax])
assert [(min(c),max(c)) for c in coords]==[(0,550),(0,100),(-20,0)]
p.write_bytes(data)
base=json.loads((OLD/'stage_fixed/stage_manifest.json').read_text());base['flatground_sha256']=H(p)
new={}
for name,seed in [('dx1p0_s103',105),('dx0p5_s103',105),('dx1p0_s104',106),('dx0p5_s104',106)]:
 target=name.rsplit('s',1)[0]+'s'+str(seed)
 (S/name).rename(S/target)
 conf=S/target/'conf.luwpf';text=conf.read_text();assert text.count('vk_inlet_seed = '+name.rsplit('s',1)[1])==1
 conf.write_text(text.replace('vk_inlet_seed = '+name.rsplit('s',1)[1],'vk_inlet_seed = '+str(seed)))
 rec=dict(base['cases'][name]);rec['seed']=seed;rec['conf_sha256']=H(conf);new[target]=rec
base['cases']=new
setup=S/'FluidX3D/src/setup.cpp';text=setup.read_text();anchor='''            emit_progress_stage("interface_interpolation",\n                                "Interface interpolation",\n                                "Profile boundary conditions completed",'''
assert text.count(anchor)==1
# Native host flags after voxelization and boundary assignment, before run_lbm.
gate='''            // T3c pre-solver geometry gate: native host flags, fixed physical x/y columns.
            {
                const float x_sites[] = {0.0f, 1.0f, 5.0f, 252.0f, 500.0f};
                const uint gy = (uint)std::lround(50.0f/cell_m);
                const uint ground_index = (uint)std::lround(20.0f/cell_m);
                std::filesystem::create_directories(parent+"/RESULTS");
                std::ofstream gate(parent+"/RESULTS/t3c_geometry_gate.csv", std::ios::out|std::ios::trunc);
                if(!gate) print_error("T3c gate cannot open output");
                gate << "x_m,y_m,first_fluid_k,first_fluid_z_m,expected_z_m,pass\\n";
                bool good = gy < Ny && ground_index+3u < Nz;
                for(const float xs : x_sites) {
                    const uint gx=(uint)std::lround(xs/cell_m);
                    uint k=Nz;
                    if(gx<Nx && gy<Ny) {
                        for(uint kz=ground_index;kz<Nz;kz++) {
                            if((lbm.flags[lbm.index(gx,gy,kz)] & TYPE_S)==0u) {k=kz;break;}
                        }
                    }
                    const float zm=k<Nz ? ((float)k-(float)ground_index)*cell_m : -999.0f;
                    const bool pass=k<Nz && std::fabs(zm-cell_m)<1.0e-4f;
                    good=good && pass;
                    gate << xs << ",50," << k << "," << zm << "," << cell_m << "," << (pass?1:0) << "\\n";
                    println("T3C_GEOMETRY x="+to_string(xs)+" first_z="+to_string(zm)+" expected="+to_string(cell_m)+" pass="+to_string(pass));
                }
                gate.flush();if(!gate) print_error("T3c gate write failed");
                if(!good) print_error("T3c geometry gate failed before solver");
            }
'''
text=text.replace(anchor,gate+anchor);setup.write_text(text)
base['setup_sha256']=H(setup)
(S/'stage_manifest.json').write_text(json.dumps(base,indent=2)+'\n')
with tarfile.open(R/'stage_t3c_bundle.tar.gz','w:gz') as tf:
 for item in sorted(S.rglob('*')):
  if item.is_file():tf.add(item,item.relative_to(S))
print(json.dumps({'stl_bounds':[(min(c),max(c)) for c in coords],'stl_sha256':H(p),'setup_sha256':H(setup),'bundle_sha256':H(R/'stage_t3c_bundle.tar.gz'),'cases':{k:v['conf_sha256'] for k,v in new.items()}},indent=2))
