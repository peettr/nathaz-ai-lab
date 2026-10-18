from pathlib import Path
import shutil,subprocess,time
r=Path('/content/luw-aij'); src=r/'repo/examples/example_ProfileResearch_noDEM'; dst=r/'case_avg'; assert not dst.exists()
(dst/'proj_temp').mkdir(parents=True); (dst/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:
 shutil.copy2(src/rel,dst/rel)
p=dst/'conf.luwpf'; p.write_text(p.read_text()+'\n// Time-mean window for wind-tunnel comparison (new isolated case)\npurge_avg_steps = 2000\npurge_avg_stride = 10\n')
# start via wrapper, isolate all output and keep initial 20001-step case intact
code='''import subprocess,time,pathlib
r=pathlib.Path('/content/luw-aij'); case=r/'case_avg'; binary=r/'repo/core/cfd_core/FluidX3D/bin/FluidX3D'; t0=time.time(); (r/'avg.start').write_text(str(t0))
with (r/'avg.log').open('w') as f: p=subprocess.run([str(binary),str(case/'conf.luwpf')],cwd=case,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
(r/'avg.exit').write_text(f'exit={p.returncode} wall_s={time.time()-t0:.2f}\\n')
'''
(r/'avg_wrapper.py').write_text(code)
f=(r/'avg_wrapper.log').open('w'); p=subprocess.Popen(['python3',str(r/'avg_wrapper.py')],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('avg pid',p.pid,'config',p,flush=True)
