from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
src=R.parent/'approach_keep/stage_E1Wv5'
out=R/'stage_probe2'
assert src.exists() and not out.exists()
shutil.copytree(src,out)
p=out/'FluidX3D/src/setup.cpp';s=p.read_text()
old='        auto monitor_city = [&]() {\n'
assert s.count(old)==1
s=s.replace(old,'#ifdef WALE_SGS\n        auto* wdom=lbm.lbm_domain[0];\n        wdom->wale_omega.add_host_buffer();\n        std::ofstream wtrace(parent+"/RESULTS/wale_probe.csv");\n        wtrace<<"step,x,y,z,flag,rho,ux,uy,uz,omega\\n";\n#endif\n'+old)
old='        auto monitor_city = [&]() {\n            if(lbm.get_D()!=1u) print_error("city monitor requires one subdomain");\n            enqueue_read_u_rho();\n'
assert s.count(old)==1
s=s.replace(old,old+'#ifdef WALE_SGS\n            lbm.lbm_domain[0]->wale_omega.read_from_device();\n#endif\n')
old='            extrema_monitor << lbm.get_t()'
assert s.count(old)==1
s=s.replace(old,'''#ifdef WALE_SGS
            for(int dz=-1;dz<=1;dz++) for(int dy=-1;dy<=1;dy++) for(int dx=-1;dx<=1;dx++) {
                int xx=38+dx,yy=76+dy,zz=21+dz;
                size_t i=idx(xx,yy,zz);
                wtrace<<lbm.get_t()<<","<<xx<<","<<yy<<","<<zz<<","<<(int)dom->flags.x[i]<<","<<dom->rho.x[i]<<","<<dom->u.x[i]<<","<<dom->u.x[mon_n+i]<<","<<dom->u.x[2*mon_n+i]<<","<<dom->wale_omega.x[i]<<"\\n";
            }
            wtrace.flush();
#endif
'''+old)
p.write_text(s)
files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp']
(R/'probe_manifest.json').write_text(json.dumps({f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files},indent=2))
with tarfile.open(R/'probe_inputs.tar.gz','w:gz') as t:
 t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
print('prepared probe')
