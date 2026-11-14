from pathlib import Path
import shutil,hashlib,json,tarfile,difflib
R=Path(__file__).resolve().parent
src=Path('./24_Urban_Wind_LBM/06_Logs/wp1b_ibm/inflow_ti/stage_B')
d=R/'stage_S1'
assert not d.exists()
shutil.copytree(src,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=d/'FluidX3D/src/defines.hpp';s=p.read_text();key='//#define GROUND_WALL_SGS_DAMP';assert s.count(key)==1;s=s.replace(key,key+'\n#define FENG_N1_GROUND_SGS_ONLY // independent n=1 harmonic mixing length');p.write_text(s)
p=d/'FluidX3D/src/lbm.cpp';s=p.read_text();key='\t"\\n\t#define GROUND_WALL_SGS_DAMP"';assert s.count(key)==1;s=s.replace(key,key+'\n#endif\n#ifdef FENG_N1_GROUND_SGS_ONLY\n\t"\\n\t#define FENG_N1_GROUND_SGS_ONLY"\n#ifdef GROUND_WALL_SGS_DAMP');p.write_text(s)
p=d/'FluidX3D/src/kernel.cpp';s=p.read_text();key=')+"#endif"+R(\n\t\tw = 2.0f/(tau0+sqrt(sq(tau0)+0.76421222f*sgs_length_factor*sqrt(Q)/rhon));';assert s.count(key)==1
insert=''' )+"#endif"+R(
)+"#ifdef FENG_N1_GROUND_SGS_ONLY"+R(
        // Feng et al. 2021 Eq. 27 n=1, only flat-ground AGL layers 1..8.
        // Numerical wall is half a cell below the first fluid center.
        const int feng_layer=(int)coordinates(n).z+def_Oz-def_ground_first_fluid_z;
        if(feng_layer>=0 && feng_layer<8 && flagsn_bo!=TYPE_E) {
            const float csdelta=sqrt(0.76421222f/(18.0f*1.41421356237f));
            const float d_wall=(float)feng_layer+0.5f; // delta=1 m
            const float kappa_z=0.41f*(d_wall+0.002f); // z0 is an assumption
            const float lambda=csdelta*kappa_z/(csdelta+kappa_z);
            sgs_length_factor=sq(lambda/csdelta);
        }
'''
s=s.replace(key,insert+key);p.write_text(s)
manifest={str(q.relative_to(d)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [d/'FluidX3D/src/defines.hpp',d/'FluidX3D/src/setup.cpp',d/'FluidX3D/src/kernel.cpp',d/'FluidX3D/src/lbm.cpp',d/'case/conf.luwpf',d/'case/wind_bc/profile.dat',d/'case/proj_temp/CaseE_PF.stl']}
(R/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'S1_inputs.tar.gz','w:gz') as t:
 t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
for name in ('defines.hpp','lbm.cpp','kernel.cpp'):
 original=(src/'FluidX3D/src'/name).read_text().splitlines(keepends=True)
 modified=(d/'FluidX3D/src'/name).read_text().splitlines(keepends=True)
 with (R/f'{name}.diff').open('w') as f:f.writelines(difflib.unified_diff(original,modified,fromfile='B2/'+name,tofile='S1/'+name))
print(manifest)
