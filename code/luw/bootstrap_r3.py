import pathlib,subprocess,time,shutil
r=pathlib.Path('/content/luw-aij-r3');r.mkdir(exist_ok=True)
def run(cmd,cwd=None):
 t=time.time();p=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);print('COMMAND',cmd,'exit',p.returncode,'wall_s',round(time.time()-t,2),'\n',p.stdout[-8000:],flush=True);assert p.returncode==0
run(['git','clone','https://github.com/hweifluids/LatticeUrbanWind.git',str(r/'repo')]);run(['git','rev-parse','HEAD'],cwd=r/'repo');run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'])
case=r/'case_fine';case.mkdir();(case/'proj_temp').mkdir();(case/'wind_bc').mkdir()
src=r/'repo/examples/example_ProfileResearch_noDEM'
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:shutil.copy2(src/rel,case/rel)
p=case/'conf.luwpf';text=p.read_text().replace('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]').replace('angle = [0, 90, 180, 270]','angle = [0]').replace('gpu_memory = 4000','gpu_memory = 35000');assert 'n_gpu = [1, 1, 1]' in text and 'angle = [0]' in text and 'gpu_memory = 35000' in text
text+='\n// r3: 26,000-step average covers ~2 km / 3.93 m/s = 509 s at estimated 47 steps/s\nrun_nstep = 32000\npurge_avg = 26000\npurge_avg_stride = 20\noutput_tke_ti_tls = []\n';p.write_text(text)
print('CONFIG\n',text,flush=True)
run(['make','Linux','-j2'],cwd=r/'repo/core/cfd_core/FluidX3D')
print('READY',str(r),flush=True)
