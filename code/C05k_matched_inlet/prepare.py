from pathlib import Path
import shutil, tarfile, hashlib, json
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]/'wp1b_ibm/resolution_c05/stage_C05'
OUT=ROOT/'stage_C05k'
assert BASE.exists() and not OUT.exists()
shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
s=OUT/'FluidX3D/src/setup.cpp'; t=s.read_text()
# B2u scalar-mean accumulation is diagnostic only; do not touch flow solver.
replacements=[
('const float* M2_u, const float* M2_v, const float* M2_w,\n', 'const float* M2_u, const float* M2_v, const float* M2_w,\n                          const float* scalar_u, const float* scalar_u2,\n'),
('    if (write_tke) write_field("tke", tke.data(), 1u, u_factor * u_factor);\n','    if (write_tke) write_field("tke", tke.data(), 1u, u_factor * u_factor);\n    if (scalar_u && scalar_u2) { write_field("speed_mean",scalar_u,1u,u_factor); write_field("speed2_mean",scalar_u2,1u,u_factor*u_factor); }\n'),
('        std::vector<float> M2_w;\n','        std::vector<float> M2_w;\n        std::vector<float> speed_mean, speed2_mean;\n'),
('            M2_w.assign((size_t)Ncells, 0.0f);\n','            M2_w.assign((size_t)Ncells, 0.0f);\n            speed_mean.assign((size_t)Ncells,0.0f); speed2_mean.assign((size_t)Ncells,0.0f);\n'),
('                u_avg[i3 + 2] = mean_w;\n','                u_avg[i3 + 2] = mean_w;\n                const float speed2=ux*ux+uy*uy+uz*uz;\n                speed_mean[n]+=(sqrtf(speed2)-speed_mean[n])*inv_n;\n                speed2_mean[n]+=(speed2-speed2_mean[n])*inv_n;\n'),
('                          M2_u.data(), M2_v.data(), M2_w.data(),\n','                          M2_u.data(), M2_v.data(), M2_w.data(),\n                          speed_mean.data(), speed2_mean.data(),\n')]
for old,new in replacements:
 assert t.count(old)==1,(old,t.count(old))
 t=t.replace(old,new)
s.write_text(t)
# Gate-only simulation: same starting transient and averaging tail scaled down; not production.
c=OUT/'case/conf.luwpf'; txt=c.read_text()
for old,new in [('run_nstep = 62000','run_nstep = 6000'),('purge_avg = 40000','purge_avg = 4000')]:
 assert txt.count(old)==1;txt=txt.replace(old,new)
c.write_text(txt)
with tarfile.open(ROOT/'gate_inputs.tar.gz','w:gz') as tar:
 tar.add(OUT/'FluidX3D',arcname='FluidX3D');tar.add(OUT/'case',arcname='case')
files=['case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','FluidX3D/src/setup.cpp']
(ROOT/'stage_hashes.json').write_text(json.dumps({x:hashlib.sha256((OUT/x).read_bytes()).hexdigest() for x in files},indent=2)+'\n')
print('stage ready')
