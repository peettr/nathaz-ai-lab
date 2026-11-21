from pathlib import Path
import tarfile,hashlib,json
R=Path(__file__).resolve().parent
B=Path('./24_Urban_Wind_LBM/06_Logs/wp1b_ibm/inflow_ti')
S=R/'stage_B2u'
assert not S.exists(), 'fresh stage required'
S.mkdir(parents=True)
with tarfile.open(B/'B2_inputs.tar.gz') as t:t.extractall(S,filter='data')
p=S/'FluidX3D/src/setup.cpp'
s=p.read_text()
def rep(old,new):
 global s
 assert s.count(old)==1,(old,s.count(old))
 s=s.replace(old,new)
rep('const float* M2_u, const float* M2_v, const float* M2_w,\n                          const ulong avg_count,', 'const float* M2_u, const float* M2_v, const float* M2_w,\n                          const float* scalar_u, const float* scalar_u2,\n                          const ulong avg_count,')
rep('if (write_tke) write_field("tke", tke.data(), 1u, u_factor * u_factor);','if (write_tke) write_field("tke", tke.data(), 1u, u_factor * u_factor);\n    if (scalar_u && scalar_u2) {\n        write_field("speed_mean", scalar_u, 1u, u_factor);\n        write_field("speed2_mean", scalar_u2, 1u, u_factor*u_factor);\n    }')
rep('std::vector<float> M2_w;\n        ulong avg_count', 'std::vector<float> M2_w;\n        std::vector<float> speed_mean, speed2_mean;\n        ulong avg_count')
rep('M2_w.assign((size_t)Ncells, 0.0f);','M2_w.assign((size_t)Ncells, 0.0f);\n            speed_mean.assign((size_t)Ncells, 0.0f);\n            speed2_mean.assign((size_t)Ncells, 0.0f);')
rep('m2_w[n] += delta_w * delta2_w;\n                u_avg[i3 + 2] = mean_w;','m2_w[n] += delta_w * delta2_w;\n                u_avg[i3 + 2] = mean_w;\n                // Diagnostic only: same instantaneous velocities and same averaging window.\n                const float speed2 = ux*ux + uy*uy + uz*uz;\n                speed_mean[n] += (sqrtf(speed2) - speed_mean[n])*inv_n;\n                speed2_mean[n] += (speed2 - speed2_mean[n])*inv_n;')
rep('M2_u.data(), M2_v.data(), M2_w.data(),\n                          avg_count, true, false, vtk_output_Nz);','M2_u.data(), M2_v.data(), M2_w.data(),\n                          speed_mean.data(), speed2_mean.data(),\n                          avg_count, true, false, vtk_output_Nz);')
p.write_text(s)
manifest={str(q.relative_to(S)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [p,S/'FluidX3D/src/kernel.cpp',S/'FluidX3D/src/defines.hpp',S/'case/conf.luwpf',S/'case/wind_bc/profile.dat',S/'case/proj_temp/CaseE_PF.stl']}
(R/'inputs_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'B2u_inputs.tar.gz','w:gz') as t:
 for q in ('FluidX3D','case'):t.add(S/q,arcname=q)
print('prepared',p.stat().st_size,(R/'B2u_inputs.tar.gz').stat().st_size,manifest)
