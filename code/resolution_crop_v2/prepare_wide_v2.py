"""One enlarged crop, preserving whole-building trimming and immutable first run."""
from pathlib import Path
import sys,shutil,json,hashlib,tarfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import prepare_v2
R=Path(__file__).resolve().parent;src=R/'stage_C1v2';dst=R/'stage_C1widev2';assert not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
prepare_v2.BOX=(0.,330.,65.,345.);prepare_v2.MARGIN=20.
stat=prepare_v2.trim(R.parent/'resolution_crop/stage_C1/case/proj_temp/CaseE_PF.stl',dst/'case/proj_temp/CaseE_PF.stl')
p=dst/'FluidX3D/src/setup.cpp';s=p.read_text()
for old,new in [('float sponge_thickness_m = 60.0f;','float sponge_thickness_m = 40.0f;'),('80.0f/cell_m','65.0f/cell_m'),('float3(0.0f, 80.0f, -20.0f)','float3(0.0f, 65.0f, -20.0f)')]:
 assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
p.write_text(s)
c=dst/'case/conf.luwpf';s=c.read_text()
for old,new in [('300.000000','330.000000'),('250.000000','280.000000'),('120.000000','120.000000')]:
 if old!=new:assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
c.write_text(s)
m={str(x.relative_to(dst)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [dst/'case/proj_temp/CaseE_PF.stl',dst/'case/wind_bc/profile.dat',c,p]}
(R/'C1widev2_manifest.json').write_text(json.dumps(m,indent=2)+'\n');(R/'C1widev2_geometry.json').write_text(json.dumps(stat,indent=2)+'\n')
with tarfile.open(R/'C1widev2_inputs.tar.gz','w:gz') as t:t.add(dst/'FluidX3D',arcname='FluidX3D');t.add(dst/'case',arcname='case')
print('wide',stat['deleted_components'],stat['retained_building_triangles'],stat['wall_to_nearest_deleted_bbox_m'],m)
