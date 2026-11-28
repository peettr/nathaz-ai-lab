#!/usr/bin/env python3
"""Create one immutable T18 C01 stage from previously checked unified variants."""
from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
V5=R.parent/'run_20261123_0117_v5'
OLD=R.parents[2]/'R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455'
assert not (R/'pack_stage').exists()
shutil.copytree(V5/'variants',R/'pack_stage')
for n in ('worker_native.py','controller_hardened.py','remote_B.py','native_analysis.py','analyze_longspin.py','machine.py'):
 shutil.copyfile(OLD/n,R/n)
for n in ('assert_T18.py',):
 shutil.copyfile(R.parents[1]/'prep_20261123_0025'/n,R/n)
assert hashlib.sha256((R/'assert_T18.py').read_bytes()).hexdigest()=='57844319f11fd53261f442dd40de16d78aad6df986d00f86936fd91e972c0e3b'
for v in ('B0','K1a','K1b','K2','K3a','K3b'):
 p=R/'pack_stage'/v/'src/t17_b_native.inc'
 s=p.read_text()
 assert s.count('const ulong initial=(mode=="smoke")?1000ul:25ul*Tsteps;')==1
 s=s.replace('const ulong initial=(mode=="smoke")?1000ul:25ul*Tsteps;','const ulong initial=(mode=="smoke")?53851ul:25ul*Tsteps;')
 s=s.replace('const ulong statsteps=(mode=="smoke")?1000ul:4ul*half;','const ulong statsteps=(mode=="smoke")?0ul:4ul*half;')
 anchor='''    for(uint attempt=0;attempt<(mode=="smoke"?1u:4u);++attempt) {'''
 assert s.count(anchor)==1
 s=s.replace(anchor,'''    if(mode=="smoke") {
        advance(initial,false);
        std::ofstream done(bdir/"producer.done");done<<step<<'\\n';done.close();
        return;
    }
'''+anchor)
 anchor2='''            lbm.run(1ul);++step;
            // Ground drag is positive'''
 assert s.count(anchor2)==1
 s=s.replace(anchor2,'''            lbm.run(1ul);++step;
            if(mode=="smoke" && (step%1000ul==0ul || step==target)) {
                lbm.update_fields();lbm.rho.read_from_device();
                float rmin=std::numeric_limits<float>::infinity();
                float rmax=-std::numeric_limits<float>::infinity();
                for(uint zz=1u;zz<=64u;++zz) for(uint yy=0u;yy<lbm.get_Ny();++yy)
                    for(uint xx=0u;xx<lbm.get_Nx();++xx) {
                        const ulong nn=lbm.index(xx,yy,zz);
                        const float rr=lbm.rho[nn];
                        if(!std::isfinite(rr)) print_error("T18_C0_NAN step="+std::to_string(step));
                        rmin=std::min(rmin,rr);rmax=std::max(rmax,rr);
                    }
                std::ofstream smoke(bdir/"rho_monitor.csv",std::ios::app);
                smoke<<step<<','<<std::setprecision(9)<<rmin<<','<<rmax<<'\\n';smoke.flush();
                if(rmin<0.9f || rmax>1.1f) print_error("T18_C0_RHO_RANGE step="+std::to_string(step));
            }
            // Ground drag is positive''')
 p.write_text(s)
# A single candidate differs only by its defines.hpp (and a shared C0 producer).
for name in ('kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp','t17_b_native.inc'):
 b=(R/'pack_stage/B0/src'/name).read_bytes()
 for v in ('K1a','K1b','K2','K3a','K3b'):
  assert (R/'pack_stage'/v/'src'/name).read_bytes()==b,(v,name)
manifest={v:{n:hashlib.sha256((R/'pack_stage'/v/'src'/n).read_bytes()).hexdigest() for n in ('kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp','t17_b_native.inc','defines.hpp')} for v in ('B0','K1a','K1b','K2','K3a','K3b')}
(R/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('stage',len(manifest),'native C0 monitor installed')
