"""Prepare isolated Case E official-profile stage; never alter predecessors."""
from pathlib import Path
import shutil, hashlib, json, tarfile
R=Path(__file__).resolve().parent
S=R/'isolate_stage_v2'; D=R/'stage3'
if not D.exists():
    shutil.copytree(S,D,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.csv','*.log'))
else:
    assert (D/'case/conf.luwpf').read_bytes()==(S/'case/conf.luwpf').read_bytes(), 'existing stage3 not fresh'
    assert (D/'FluidX3D/src/setup.cpp').read_bytes()==(S/'FluidX3D/src/setup.cpp').read_bytes(), 'existing stage3 already modified'
old=S/'case/wind_bc/profile.dat'
new=R.parents[2]/'04_Handoffs/from_22_Lab_20261015/06_Logs_luw/wallmodel/LatticeUrbanWind_HEAD_gate/examples/example_ProfileResearch_noDEM/wind_bc/profile.dat'
assert new.exists(),new
shutil.copy2(new,D/'case/wind_bc/profile.dat')
assert (D/'case/conf.luwpf').read_bytes()==(S/'case/conf.luwpf').read_bytes()
p=D/'FluidX3D/src/setup.cpp';s=p.read_text()
needle='            initialize_profile_velocity(lbm, ground_xy, dir_x, dir_y);\n            apply_profile_boundaries(lbm, ground_xy, dir_x, dir_y, case_downstream_bc);'
assert s.count(needle)==1
s=s.replace(needle,needle+'''\n#ifdef CITY_STABILITY_MONITOR
            // Host flags after actual device voxelization and profile BC, before solver initialization.
            // Only the bottom 22 planes; exact x-fastest byte layout is documented in stage3 runner.
            if (lbm.get_D()!=1u || Nx!=500u || Ny!=500u || Nz<22u) print_error("stage3 flag export grid mismatch");
            {
                std::ofstream ff(parent+"/RESULTS/native_flags_z0_21.bin",std::ios::binary|std::ios::trunc);
                if(!ff) print_error("cannot open native flag file");
                for(uint zf=0u;zf<22u;zf++) for(uint yf=0u;yf<Ny;yf++) for(uint xf=0u;xf<Nx;xf++) {
                    const uchar fl=lbm.flags[(ulong)xf+(ulong)Nx*((ulong)yf+(ulong)Ny*(ulong)zf)];
                    ff.write((const char*)&fl,1);
                }
                ff.flush();if(!ff) print_error("flag export failed");
            }
#endif''')
assert s.count('lbm.get_t()%200ull==0ull) monitor_city();')==2
s=s.replace('lbm.get_t()%200ull==0ull) monitor_city();','lbm.get_t()%50ull==0ull) monitor_city();')
# This is a readback of macro fields every 50 steps, NOT an on-device any-reduction.
p.write_text(s)
manifest={'profile_old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'profile_stage3_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'source':str(S),'config_sha256':hashlib.sha256((D/'case/conf.luwpf').read_bytes()).hexdigest(),'monitor':'host readback full macro fields every 50 steps; NOT device reduction'}
(R/'stage3_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=R/'city_stage3_inputs.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
    tar.add(D/'FluidX3D',arcname='FluidX3D');tar.add(D/'case',arcname='case')
manifest['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
(R/'stage3_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(manifest)
