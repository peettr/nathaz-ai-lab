"""Build isolated Case E crop stages; source B2 remains read-only."""
from pathlib import Path
import shutil, hashlib, json, tarfile, re
R=Path(__file__).resolve().parent
SRC=R.parent/'inflow_ti/stage_B'
BOX=(0,300,80,330,180)

def replace_once(s,a,b):
 assert s.count(a)==1,(a,s.count(a))
 return s.replace(a,b)

def stage(tag,dx):
 d=R/f'stage_{tag}'
 assert not d.exists(),d
 shutil.copytree(SRC,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 conf=d/'case/conf.luwpf';c=conf.read_text()
 for old,new in [('si_x_cfd = [0.000000, 500.000000]','si_x_cfd = [0.000000, 300.000000]'),('si_y_cfd = [0.000000, 500.000000]','si_y_cfd = [0.000000, 250.000000]'),('si_z_cfd = [0.000000, 270.000000]','si_z_cfd = [0.000000, 120.000000]'),('cell_size = 1.0',f'cell_size = {dx}'),('purge_avg = 20000',f'purge_avg = {round(20000/dx)}'),('run_nstep = 31000',f'run_nstep = {round(31000/dx)}'),('purge_avg_stride = 40',f'purge_avg_stride = {round(40/dx)}')]:c=replace_once(c,old,new)
 conf.write_text(c)
 p=d/'FluidX3D/src/setup.cpp';s=p.read_text()
 s=replace_once(s,'float sponge_thickness_m = 200.0f;','float sponge_thickness_m = 60.0f; // crop top: same physical core 120 m')
 # Full STL remains intact. Rigid original physical coordinate -> crop lattice coordinate.
 old='''    const float target_lbm_x = units.x(si_size.x);
    const float scale_geom = target_lbm_x / stl_size_si.x;
    mesh->scale(scale_geom);
    mesh->translate(float3(1.0f - mesh->pmin.x, 1.0f - mesh->pmin.y, 1.0f - mesh->pmin.z));'''
 new='''    // Crop: retain source STL unchanged; NO bounding-box normalization.
    // Original STL physical coordinates x,y=[0,500], z=[-20,60] m.
    // x crop begins 0m, y crop begins 80m; original z=-20m is lattice 1.
    const float scale_geom = 1.0f / cell_m;
    mesh->scale(scale_geom);
    mesh->translate(float3(1.0f, 1.0f - 80.0f/cell_m, 1.0f + 20.0f/cell_m));'''
 s=replace_once(s,old,new)
 # Geometry original physical coordinate of lattice first centre = (0,80,-20) rather than STL pmin.
 s=replace_once(s,'vtk_origin_shift = stl_min_si - domain_min_si;',
 '''vtk_origin_shift = float3(0.0f, 80.0f, -20.0f) - domain_min_si;''')
 s=replace_once(s,'const float z_agl = std::max(0.0f,p.z - 20.0f);',
 '''const float z_agl = std::max(0.0f,(p.z - 20.0f/cfg_.cell_size_m) * cfg_.cell_size_m);''')
 s=replace_once(s,'float official_sigma_scale = 0.0f;', 'float official_sigma_scale = 0.0f;\n        float cell_size_m = 1.0f;')
 s=replace_once(s,'cfg.official_sigma_scale = units.u(7.8f); // UR, same SI->lattice mapping as baseline',
 '''cfg.official_sigma_scale = units.u(7.8f); // UR, same SI->lattice mapping as baseline
        cfg.cell_size_m = cell_m;''')
 # Downstream field/sample reporting must remain in physical global coordinates via vtk_origin_shift.
 p.write_text(s)
 manifest={}
 for name in ['FluidX3D/src/defines.hpp','FluidX3D/src/setup.cpp','FluidX3D/src/kernel.cpp','case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl']:
  manifest[name]=hashlib.sha256((d/name).read_bytes()).hexdigest()
 (R/f'{tag}_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 with tarfile.open(R/f'{tag}_inputs.tar.gz','w:gz') as t:
  t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag,manifest)

if __name__=='__main__':
 stage('C1',1.0)
 # C05 MUST be created only after C1 consistency gate passes.
