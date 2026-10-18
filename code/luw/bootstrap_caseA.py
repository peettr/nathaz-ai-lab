"""Create a fresh LUW Case A deck on Colab, no solver source edits."""
from pathlib import Path
import subprocess, shutil, time
r=Path('/content/luw-aij-caseA');assert not r.exists();r.mkdir()
def run(cmd,cwd=None):
    t=time.time();p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print('COMMAND',cmd,'EXIT',p.returncode,'WALL_S',round(time.time()-t,2),'OUTPUT',p.stdout[-3000:],flush=True);assert p.returncode==0
run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'])
run(['git','clone','https://github.com/hweifluids/LatticeUrbanWind.git',str(r/'repo')]);run(['git','rev-parse','HEAD'],r/'repo')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r/'repo',text=True).strip()=='dd438c1c68664980a92460e4778f18f36be3f47c'
run(['make','Linux','-j2'],r/'repo/core/cfd_core/FluidX3D')
case=r/'caseA';(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
for src,dst in [('/content/CaseA_PF_caseA.stl',case/'proj_temp/CaseA_PF.stl'),('/content/profile_caseA.dat',case/'wind_bc/profile.dat')]:shutil.copy2(src,dst)
c=r/'repo/examples/example_ProfileResearch_noDEM/conf.luwpf';txt=c.read_text()
changes=[('casename = CaseE','casename = CaseA'),('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1088.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 704.000000]'),('si_z_cfd = [0.000000, 270.000000]','si_z_cfd = [0.000000, 384.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 2.0\n'),('angle = [0, 90, 180, 270]','angle = [270]')]
for old,new in changes:assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
# Expected ~39 steps/s from Case E one-meter timing (78 steps/s): 22000 steps = ~564 s > 2*1088/4.491 = 484.5 s.
txt+='\nrun_nstep = 32000\npurge_avg = 22000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\n'
(case/'conf.luwpf').write_text(txt);print('CONFIG',txt,flush=True)
