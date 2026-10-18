from pathlib import Path
import subprocess,time,shutil,numpy as np,struct
r=Path('/content/luw-aij-r4b');r.mkdir(exist_ok=True)
def run(cmd,cwd=None):
 t=time.time();p=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);print('COMMAND',cmd,'exit',p.returncode,'wall_s',round(time.time()-t,2),'\n',p.stdout[-1000:],flush=True);assert p.returncode==0
run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader']);run(['git','clone','https://github.com/hweifluids/LatticeUrbanWind.git',str(r/'repo')]);run(['git','rev-parse','HEAD'],r/'repo');run(['make','Linux','-j2'],r/'repo/core/cfd_core/FluidX3D')
source=r/'repo/examples/example_ProfileResearch_noDEM';case=r/'case_west';(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:shutil.copy2(source/rel,case/rel)
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]);p=case/'proj_temp/CaseE_PF.stl';a=np.fromfile(p,dtype=D,offset=84).copy();assert len(a)==9210
x0,x1,y0,y1=300.,1500.,650.,1350.;v=a['v'];assert np.all((v[:-12,:,0]>x0)&(v[:-12,:,0]<x1)&(v[:-12,:,1]>y0)&(v[:-12,:,1]<y1));v[:,:,0]-=x0;v[:,:,1]-=y0
for component,old_low,old_high,span in [(0,-x0,2022.5001-x0,x1-x0),(1,-y0,1996.5001-y0,y1-y0)]:
 z=v[-12:,:,component];z[np.isclose(z,old_low,atol=.01)]=0;z[np.isclose(z,old_high,atol=.01)]=span
assert np.allclose(v[-12:].min(axis=(0,1))[:2],[0,0]) and np.allclose(v[-12:].max(axis=(0,1))[:2],[x1-x0,y1-y0]);q=case/'proj_temp/cropped.stl'
with q.open('wb') as f:f.write(b'LUW Case E cropped box r4b'.ljust(80,b' '));f.write(struct.pack('<I',len(a)));a.tofile(f)
p.unlink();q.rename(p)
c=case/'conf.luwpf';txt=c.read_text().replace('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1200.000000]').replace('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 700.000000]').replace('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]').replace('angle = [0, 90, 180, 270]','angle = [270]').replace('mesh_control = "gpu_memory"','mesh_control = "cell_size"').replace('gpu_memory = 4000','gpu_memory = 60000').replace('cell_size =\n','cell_size = 1.0\n')
# Need 1200/3.92864=305.45s, time conversion 78steps/s => 23826 steps; use 25k avg.
c.write_text(txt+'\nrun_nstep = 30000\npurge_avg = 25000\npurge_avg_stride = 40\noutput_tke_ti_tls = []\n');print('CROP',x0,x1,y0,y1,'CONFIG',c.read_text(),'READY',flush=True)
