"""Clone immutable LUW HEAD, build, crop only Case E outer base, configure west 1 m."""
from pathlib import Path
import subprocess,time,shutil,numpy as np,struct
r=Path('/content/luw-aij-r6');assert not r.exists();r.mkdir()
def run(cmd,cwd=None):
 t=time.time();p=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 print('COMMAND',cmd,'exit',p.returncode,'wall_s',round(time.time()-t,2),'\n',p.stdout[-2000:],flush=True);assert p.returncode==0
run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'])
run(['git','clone','https://github.com/hweifluids/LatticeUrbanWind.git',str(r/'repo')]);run(['git','rev-parse','HEAD'],r/'repo')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r/'repo',text=True).strip()=='dd438c1c68664980a92460e4778f18f36be3f47c'
run(['make','Linux','-j2'],r/'repo/core/cfd_core/FluidX3D')
base=r/'repo/examples/example_ProfileResearch_noDEM';case=r/'case_west';(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:shutil.copy2(base/rel,case/rel)
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]);p=case/'proj_temp/CaseE_PF.stl';a=np.fromfile(p,dtype=D,offset=84).copy();assert len(a)==9210
x0,x1,y0,y1=300.,1260.,750.,1250.;v=a['v'];assert np.all((v[:-12,:,0]>x0)&(v[:-12,:,0]<x1)&(v[:-12,:,1]>y0)&(v[:-12,:,1]<y1))
print('BUILDING_BOUNDS_PF',v[:-12].min(axis=(0,1)),v[:-12].max(axis=(0,1)),flush=True)
v[:,:,0]-=x0;v[:,:,1]-=y0
for component,old_low,old_high,span in [(0,-x0,2022.5001-x0,x1-x0),(1,-y0,1996.5001-y0,y1-y0)]:
 z=v[-12:,:,component];z[np.isclose(z,old_low,atol=.01)]=0;z[np.isclose(z,old_high,atol=.01)]=span
assert np.allclose(v[-12:].min(axis=(0,1))[:2],[0,0]) and np.allclose(v[-12:].max(axis=(0,1))[:2],[960,500])
q=p.with_name('cropped.stl')
with q.open('wb') as f:f.write(b'LUW Case E west-extended base r6'.ljust(80,b' '));f.write(struct.pack('<I',len(a)));a.tofile(f)
p.unlink();q.rename(p)
c=case/'conf.luwpf';txt=c.read_text()
for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 960.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 500.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
 assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
# Prior 1 SI second ~78 steps. (31000-11000)/78=256.4s >960/3.92864=244.4s.
c.write_text(txt+'\nrun_nstep = 31000\npurge_avg = 11000\npurge_avg_stride = 40\noutput_tke_ti_tls = []\n')
print('CROP PF',x0,x1,y0,y1,'west_buffer_m',float(809.00006-x0),'triangles',len(a),'CONFIG',c.read_text(),flush=True)
