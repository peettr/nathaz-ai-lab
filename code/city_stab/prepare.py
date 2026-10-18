"""Prepare isolated city source and exact-source diff; no solver on 工作站."""
from pathlib import Path
import shutil, difflib, hashlib, tarfile
R=Path(__file__).resolve().parent
B=R.parent
SRC=B/'stress_budget/stage_mixing07/FluidX3D'
HEAD=Path('./.cache/dwt-luw-eval/core/cfd_core/FluidX3D')
CITY=B/'city_diag/stage_mix07/case'
DST=R/'stage2/FluidX3D'; assert not DST.exists()
shutil.copytree(SRC,DST,ignore=shutil.ignore_patterns('bin','obj','__pycache__'))
shutil.copytree(CITY,R/'stage2/case')
def replace(path,old,new):
 p=DST/'src'/path;s=p.read_text();assert s.count(old)==1,(path,s.count(old));p.write_text(s.replace(old,new))
def remove_between(path,start,end):
 p=DST/'src'/path;s=p.read_text(); assert s.count(start)==1,(path,start);a=s.index(start);assert end in s[a:],(path,end);b=s.index(end,a)+len(end);p.write_text(s[:a]+s[b:])
replace('kernel.cpp', ', global float* stress_nut_probe', '')
remove_between('kernel.cpp', ')+"#ifdef GROUND_WALL_MODEL"+R(\n    { const uint3 xyz=coordinates(n);', ')+"#endif"+R(\n)+"#endif"+R( // SUBGRID')
# Restore the SUBGRID terminator removed with the probe.
p=DST/'src/kernel.cpp';s=p.read_text();old='\n\n)+"#if defined(SRT)"+R(';assert old in s;s=s.replace(old,'\n)+"#endif"+R( // SUBGRID\n\n)+"#if defined(SRT)"+R(',1);p.write_text(s)
replace('lbm.cpp','\tstress_nut_probe = Memory<float>(device, 450ul);\n\tkernel_stream_collide.add_parameters(stress_nut_probe);\n','')
replace('lbm.hpp','\tMemory<float> stress_nut_probe; // 3 x locations, 5 y lines, 30 heights; lattice units\n','')
remove_between('setup.cpp','        std::vector<double> stress_u(450,0.),','        auto accumulate_from_buffers = [&]() {')
p=DST/'src/setup.cpp';s=p.read_text();old='''            if(avg_count==0ull) {
                std::fill(stress_u.begin(),stress_u.end(),0.);
                std::fill(stress_w.begin(),stress_w.end(),0.);
                std::fill(stress_uw.begin(),stress_uw.end(),0.);
                std::fill(stress_nut.begin(),stress_nut.end(),0.);
            }
            accumulate_stress();
''';assert s.count(old)==1;s=s.replace(old,'');s=s.replace('        write_stress();\n','');p.write_text(s)
# Wall accumulation is dimension-derived, but the flat-ground printout and fixed
# 200/300/400 point table are inappropriate for Case E. Retain only bounded full-plane totals.
remove_between('setup.cpp','            std::ofstream along(parent+"/RESULTS/wall_force_x.csv");','            std::ofstream out(parent+"/RESULTS/wall_tau_actual.csv");')
remove_between('setup.cpp','            for(uint x : {200u,300u,400u})','        };\n#endif')
p=DST/'src/setup.cpp';s=p.read_text();old='''            for(size_t i=0;i<xy;i++) {
''';# add safe flat plane loop with no sampling assumptions
insert='''            const size_t nx=(size_t)lbm.get_Nx(),ny=(size_t)lbm.get_Ny();
            for(size_t y=0;y<ny;y++) for(size_t x=0;x<nx;x++) {
                const size_t i=x+nx*y;
                if(i>=xy) print_error("ground diagnostic index exceeds plane");
                const float count=d->ground_tau_count.x[i];
                if(count<=0.0f) continue;
                const float tau=d->ground_tau_sum.x[i]/count;
                out << x << ',' << y << ',' << count << ',' << tau << ','
                    << d->ground_tau_sum.y[i]/count << ',' << d->ground_tau_sum.z[i]/count << ','
                    << units.si_u(std::sqrt(std::max(tau,0.0f))) << '\\n';
            }
        };
#endif'''
needle='''            out << "x,y,count,tau_abs_over_rho_lattice,fx_over_rho_lattice,fy_over_rho_lattice,ustar_mps\\n";
''';assert s.count(needle)==1;s=s.replace(needle,needle+insert);p.write_text(s)
# Runtime coefficient is applied in SGS, not compiled into three otherwise distinct kernels.
replace('kernel.cpp','0.70f*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)','def_ground_mix_a*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)')
replace('lbm.cpp','float experimental_ground_z0_lattice = 0.024f;','float experimental_ground_z0_lattice = 0.024f;\nfloat experimental_ground_mix_a = 0.0f;')
replace('lbm.cpp','"\\n\\t#define def_ground_kappa 0.4f"','"\\n\\t#define def_ground_kappa 0.4f"\n\t"\\n\\t#define def_ground_mix_a " + to_string(experimental_ground_mix_a,9u) + "f"')
replace('setup.cpp','        experimental_ground_z0_lattice = units.x(0.024f);','''        experimental_ground_z0_lattice = units.x(0.024f);
        extern float experimental_ground_mix_a;
        const char* mix_text=std::getenv("LUW_GROUND_MIX_A");
        if(!mix_text) print_error("LUW_GROUND_MIX_A must be explicitly set");
        char* mix_end=nullptr;
        experimental_ground_mix_a=std::strtof(mix_text,&mix_end);
        if(mix_end==mix_text || *mix_end || !std::isfinite(experimental_ground_mix_a) || experimental_ground_mix_a<0.0f || experimental_ground_mix_a>1.0f)
            print_error("Invalid LUW_GROUND_MIX_A");''')
# Emit exact HEAD-relative source diff with stable conventional paths.
chunks=[]
for name in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'):
 a=(HEAD/'src'/name).read_text().splitlines(keepends=True);b=(DST/'src'/name).read_text().splitlines(keepends=True)
 chunks.extend(difflib.unified_diff(a,b,fromfile='a/src/'+name,tofile='b/src/'+name))
(R/'solver_city_clean.diff').write_text(''.join(chunks))
assert 'stress_nut_probe' not in ''.join((DST/'src'/n).read_text() for n in ('kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'))
with tarfile.open(R/'city_clean_inputs.tar.gz','w:gz') as t:
 t.add(DST,arcname='FluidX3D');t.add(R/'stage2/case',arcname='case')
print('diff',len(chunks),'tar_sha256',hashlib.sha256((R/'city_clean_inputs.tar.gz').read_bytes()).hexdigest())
