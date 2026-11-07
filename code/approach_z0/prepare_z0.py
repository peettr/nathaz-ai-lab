from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
S=R.parent/'approach_full/stage_FG0A70'
for tag,a in [('FG0z','0.0'),('FG0zA70','0.70')]:
 d=R/('stage_'+tag)
 assert not d.exists(),d
 shutil.copytree(S,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 p=d/'FluidX3D/src/setup.cpp';s=p.read_text();old='experimental_ground_z0_lattice = units.x(0.024f);';assert s.count(old)==1
 new='''const char* z0_text=std::getenv("LUW_GROUND_Z0_SI");
        if(!z0_text) print_error("LUW_GROUND_Z0_SI required");
        char* z0_end=nullptr;
        const float z0_si=std::strtof(z0_text,&z0_end);
        if(z0_end==z0_text || *z0_end || !std::isfinite(z0_si) || z0_si<=0.0f || z0_si>=1.0f)
            print_error("Invalid LUW_GROUND_Z0_SI");
        experimental_ground_z0_lattice = units.x(z0_si);
        println("| Ground z0 SI="+to_string(z0_si,9u)+" m |");'''
 p.write_text(s.replace(old,new))
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 m={'tag':tag,'a':a,'z0_si':0.0001403048803922269,'files':{f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in files}}
 (R/(tag+'_manifest.json')).write_text(json.dumps(m,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag,m,flush=True)
