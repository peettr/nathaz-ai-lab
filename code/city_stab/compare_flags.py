"""Colab-only paired 200-step debug export; identical flag exporter in both."""
from pathlib import Path
import shutil,subprocess,os,hashlib,json,time
R=Path('/content/luw_citystab_flags_v4');R.mkdir(exist_ok=False)
for tag in ('head','off'):
 source=Path('/content/luw_citystab_v1')/tag
 root=R/tag
 shutil.copytree(source/'FluidX3D',root/'FluidX3D',ignore=shutil.ignore_patterns('temp','bin'))
 shutil.copytree(source/'case',root/'case',ignore=shutil.ignore_patterns('RESULTS','VTK*'))
 p=root/'FluidX3D/src/setup.cpp';s=p.read_text()
 needle='        write_final_transient();'
 assert s.count(needle)==2
 insertion='''        lbm.flags.read_from_device();
        { std::ofstream fs(parent+"/RESULTS/flag_200.bin",std::ios::binary);
          std::vector<unsigned char> flags_copy(lbm.get_N());
          for(ulong i=0;i<lbm.get_N();++i) flags_copy[i]=lbm.flags.x[i];
          fs.write(reinterpret_cast<const char*>(flags_copy.data()),(std::streamsize)flags_copy.size()); }
'''
 # both GRAPHICS and non-GRAPHICS branches
 s=s.replace(needle,insertion+needle);p.write_text(s)
 print(tag,'build',flush=True)
 with (root/'build.log').open('w') as f:q=subprocess.run(['make','Linux','-j4'],cwd=root/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 print(tag,'build_exit',q.returncode,flush=True)
 if q.returncode:print((root/'build.log').read_text()[-2000:]);break
 env=os.environ.copy();env['LUW_GROUND_MIX_A']='0'
 with (root/'solver.log').open('w') as f:q=subprocess.run([str(root/'FluidX3D/bin/FluidX3D'),str(root/'case/conf.luwpf')],cwd=root/'case',env=env,stdout=f,stderr=subprocess.STDOUT,timeout=900)
 print(tag,'solve_exit',q.returncode,flush=True)
 if q.returncode:print((root/'solver.log').read_text()[-2000:]);break
 flag=root/'case/RESULTS/flag_200.bin';print(tag,'flag_bytes',flag.stat().st_size,'sha',hashlib.sha256(flag.read_bytes()).hexdigest(),flush=True)
else:
 a=(R/'head/case/RESULTS/flag_200.bin').read_bytes();b=(R/'off/case/RESULTS/flag_200.bin').read_bytes()
 (R/'flags_comparison.json').write_text(json.dumps({'bytes':len(a),'head_sha':hashlib.sha256(a).hexdigest(),'off_sha':hashlib.sha256(b).hexdigest(),'identical':a==b},indent=2))
 print('FLAG_EQUAL',a==b,flush=True)
