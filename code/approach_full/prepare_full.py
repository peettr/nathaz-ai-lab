from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
src=R.parent/'approach_keep2/stage_E1G0A70'
for tag,a in [('FG0A70','0.70'),('FG0A100','1.0')]:
 d=R/('stage_'+tag)
 assert not d.exists()
 shutil.copytree(src,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 conf=d/'case/conf.luwpf';s=conf.read_text()
 for old,new in [('si_x_cfd = [0.000000, 300.000000]','si_x_cfd = [0.000000, 500.000000]'),('si_y_cfd = [0.000000, 250.000000]','si_y_cfd = [0.000000, 500.000000]'),('si_z_cfd = [0.000000, 120.000000]','si_z_cfd = [0.000000, 270.000000]')]:
  assert s.count(old)==1; s=s.replace(old,new)
 conf.write_text(s)
 setup=d/'FluidX3D/src/setup.cpp';s=setup.read_text()
 old='float sponge_thickness_m = 60.0f; // crop top: same physical core 120 m';assert s.count(old)==1;s=s.replace(old,'float sponge_thickness_m = 200.0f;')
 old='vtk_origin_shift = float3(0.0f, 80.0f, -20.0f) - domain_min_si;';assert s.count(old)==1;s=s.replace(old,'vtk_origin_shift = float3(0.0f, 0.0f, -20.0f) - domain_min_si;')
 old='mesh->translate(float3(1.0f, 1.0f - 80.0f/cell_m, 1.0f + 20.0f/cell_m));';assert s.count(old)==1;s=s.replace(old,'mesh->translate(float3(1.0f, 1.0f, 1.0f + 20.0f/cell_m));')
 old='if (lbm.get_D()!=1u || Nz<91u) print_error("crop flag export grid mismatch");';assert s.count(old)==1;s=s.replace(old,'if (lbm.get_D()!=1u || Nx!=500u || Ny!=500u || Nz<91u) print_error("full flag export grid mismatch");')
 setup.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 m={'tag':tag,'a':a,'files':{f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in files}}
 (R/(tag+'_manifest.json')).write_text(json.dumps(m,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag,m,flush=True)
