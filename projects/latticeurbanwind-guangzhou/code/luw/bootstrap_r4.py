from pathlib import Path
import subprocess,time,shutil
r=Path('/content/luw-aij-r4');r.mkdir(exist_ok=True)
def run(cmd,cwd=None):
 t=time.time();p=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);print('COMMAND',cmd,'exit',p.returncode,'wall_s',round(time.time()-t,2),'\n',p.stdout[-5000:],flush=True);return p
for cmd in [['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'],['free','-h']]:run(cmd)
p=run(['git','clone','https://github.com/hweifluids/LatticeUrbanWind.git',str(r/'repo')]);assert p.returncode==0
run(['git','rev-parse','HEAD'],r/'repo')
p=run(['make','Linux','-j2'],r/'repo/core/cfd_core/FluidX3D');assert p.returncode==0
src=r/'repo/examples/example_ProfileResearch_noDEM';dst=r/'case_west';(dst/'proj_temp').mkdir(parents=True);(dst/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:shutil.copy2(src/rel,dst/rel)
print('READY',flush=True)
