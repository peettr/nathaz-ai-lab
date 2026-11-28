#!/usr/bin/env python3
"""Stage isolated actual-OpenCL try12 variants; never execute locally."""
from pathlib import Path
import shutil, hashlib, json, tarfile, difflib
R=Path(__file__).resolve().parent
S=R.parent/'try11/FluidX3D_gate0_noshear'
assert S.is_dir()
for variant in ('noshear','native'):
    D=R/f'FluidX3D_{variant}'
    assert not D.exists(),D
    shutil.copytree(S,D)
    src=D/'src'; sp=src/'setup.cpp'; kp=src/'kernel.cpp'
    old=sp.read_text(); t=old
    t=t.replace('try11_noshear_wall_gate0.csv',f'try12_{variant}_wall.csv').replace('try11_noshear_pulse.csv',f'try12_{variant}_pulse.csv')
    if variant=='native':
        k=kp.read_text()
        for a,b in [('ground_first_fluid=flat_ground_eligible(n,flags);','ground_first_fluid=false; // native bounce control'),('if((int)ground_xyz.z+def_Oz==def_Nz-2 && (flags[j[5]]&TYPE_BO)==TYPE_S) {','if(false) { // native bounce control at top')]:
            assert k.count(a)==1,a
            k=k.replace(a,b)
        kp.write_text(k)
    # Prefix pulse with pre-injection and post-injection target reads plus fluid rho ledger.
    a=t.index('    if(!zero_wall) {\n        std::ofstream pulse(',t.index('void main_setup()'))
    b=t.index('    return;\n#endif',a)
    if variant=='native':
        t=t[:a]+t[b:]
    else:
        pulse='''    if(!zero_wall) {
        std::ofstream pulse("/content/try12_noshear_pulse.csv");
        if(!pulse) print_error("cannot open pulse evidence");
        pulse<<std::setprecision(17)<<"parity,variant,source_slot_before,source_slot_after_injection,target_before,target_after_injection,target_after_step,fluid_rho_before,fluid_rho_after_injection,fluid_rho_after_step,ddf_before,ddf_after_injection,ddf_after_step\\n";
        for(uint parity=0u;parity<2u;parity++) for(uint variant=0u;variant<2u;variant++) {
            LBM impulse(24u,24u,12u,0.02f);
            for(ulong n=0;n<impulse.get_N();n++) {
                uint x,y,z;impulse.coordinates(n,x,y,z);
                if(z==0u || z+1u==impulse.get_Nz()) impulse.flags[n]=TYPE_S;
                impulse.rho[n]=1.0f;impulse.u.x[n]=0.035f;
            }
            impulse.run(0u,2u);
            if(parity) impulse.run(1u,2u);
            auto& packet=impulse.lbm_domain[0]->diagnostic_fi();
            packet.add_host_buffer();packet.read_from_device();
            const ulong ground=impulse.index(9u,8u,0u), target=impulse.index(9u,8u,1u);
            const uint storage_dir=parity ? 15u : 16u;
            const ulong address=(ulong)storage_dir*impulse.get_N()+ground;
            auto mass=[&]() {
                impulse.rho.read_from_device();
                double v=0.0;
                for(ulong n=0;n<impulse.get_N();n++) if((impulse.flags[n]&(TYPE_S|TYPE_E))==0u) v+=impulse.rho[n];
                return v;
            };
            auto ddf=[&]() { double v=0.0;for(ulong i=0;i<packet.range();i++)v+=(double)packet[i];return v; };
            impulse.lbm_domain[0]->ground_pulse.read_from_device();
            const double target_before=impulse.lbm_domain[0]->ground_pulse[target];
            const double slot_before=packet[address],fluid_before=mass(),ddf_before=ddf();
            if(variant) {packet[address]+=0.01f;packet.write_to_device();}
            const double slot_after=packet[address],fluid_injected=mass(),ddf_injected=ddf();
            impulse.lbm_domain[0]->ground_pulse.read_from_device();
            const double target_injected=impulse.lbm_domain[0]->ground_pulse[target];
            impulse.run(1u,2u);
            impulse.lbm_domain[0]->ground_pulse.read_from_device();
            const double target_after=impulse.lbm_domain[0]->ground_pulse[target];
            packet.read_from_device();
            pulse<<parity<<","<<variant<<","<<slot_before<<","<<slot_after<<","<<target_before<<","<<target_injected<<","<<target_after<<","<<fluid_before<<","<<fluid_injected<<","<<mass()<<","<<ddf_before<<","<<ddf_injected<<","<<ddf()<<"\\n";
            pulse.flush();
        }
    }
'''
        t=t[:a]+pulse+t[b:]
    assert t!=old
    sp.write_text(t)
    (R/f'{variant}.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),t.splitlines(True),fromfile='try11/setup.cpp',tofile=f'try12/{variant}/setup.cpp')))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (sp,kp,src/'lbm.cpp',src/'defines.hpp')}
    archive=R/f'try12_{variant}.tar.gz'
    with tarfile.open(archive,'w:gz') as tf:tf.add(D,arcname='FluidX3D_gate0')
    (R/f'{variant}_manifest.json').write_text(json.dumps({'sources':hashes,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+'\n')
    print(variant,hashes,archive.stat().st_size)
