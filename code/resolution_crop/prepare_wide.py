from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
src=R/'stage_C1';dst=R/'stage_C1wide';assert not dst.exists();shutil.copytree(src,dst)
p=dst/'FluidX3D/src/setup.cpp';s=p.read_text();assert s.count('1.0f - 80.0f/cell_m')==1 and s.count('float3(0.0f, 80.0f, -20.0f)')==1
s=s.replace('1.0f - 80.0f/cell_m','1.0f - 55.0f/cell_m').replace('float3(0.0f, 80.0f, -20.0f)','float3(0.0f, 55.0f, -20.0f)');p.write_text(s)
p=dst/'case/conf.luwpf';s=p.read_text();assert s.count('si_y_cfd = [0.000000, 250.000000]')==1;s=s.replace('si_y_cfd = [0.000000, 250.000000]','si_y_cfd = [0.000000, 300.000000]');p.write_text(s)
m={name:hashlib.sha256((dst/name).read_bytes()).hexdigest() for name in ['FluidX3D/src/defines.hpp','FluidX3D/src/setup.cpp','FluidX3D/src/kernel.cpp','case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl']}
(R/'C1wide_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
with tarfile.open(R/'C1wide_inputs.tar.gz','w:gz') as t:t.add(dst/'FluidX3D',arcname='FluidX3D');t.add(dst/'case',arcname='case')
print(m)
