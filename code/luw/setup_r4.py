from pathlib import Path
import numpy as np,struct,subprocess,time
r=Path('/content/luw-aij-r4');case=r/'case_west';src=case/'proj_temp/CaseE_PF.stl';dst=case/'proj_temp/CaseE_PF_cropped.stl'
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]);a=np.fromfile(src,dtype=D,offset=84).copy();assert len(a)==9210
x0,x1,y0,y1=300.,1700.,500.,1500.
assert np.all((a[:-12]['v'][:,:,0]>x0)&(a[:-12]['v'][:,:,0]<x1)&(a[:-12]['v'][:,:,1]>y0)&(a[:-12]['v'][:,:,1]<y1))
v=a['v'];v[:,:,0]-=x0;v[:,:,1]-=y0
for component,old_low,old_high,span in [(0,-x0,2022.5001-x0,x1-x0),(1,-y0,1996.5001-y0,y1-y0)]:
 z=v[-12:,:,component];z[np.isclose(z,old_low,atol=.01)]=0;z[np.isclose(z,old_high,atol=.01)]=span
assert np.allclose(v[-12:].min(axis=(0,1))[:2],[0,0]) and np.allclose(v[-12:].max(axis=(0,1))[:2],[x1-x0,y1-y0])
with dst.open('wb') as f:f.write(b'LUW Case E cropped base; r4'.ljust(80,b' '));f.write(struct.pack('<I',len(a)));a.tofile(f)
src.unlink() # New ephemeral case only: remove redundant full-domain STL so solver finds cropped input only
new=dst.rename(src)
p=case/'conf.luwpf';txt=p.read_text();txt=txt.replace('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1400.000000]').replace('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 1000.000000]').replace('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]').replace('angle = [0, 90, 180, 270]','angle = [270]').replace('mesh_control = "gpu_memory"','mesh_control = "cell_size"').replace('gpu_memory = 4000','gpu_memory = 70000').replace('cell_size =\n','cell_size = 1.0\n')
assert 'angle = [270]' in txt and 'cell_size = 1.0' in txt
# 1400/3.929=356 s advection; run_nstep/purge_avg to be set after short runtime benchmark
p.write_text(txt+'\nrun_nstep = 34000\npurge_avg = 29000\npurge_avg_stride = 40\noutput_tke_ti_tls = []\n')
print('CROP',x0,x1,y0,y1,'TRIANGLES',len(a),'building bounds local',v[:-12].min(axis=(0,1)),v[:-12].max(axis=(0,1)),'CONFIG',p.read_text(),flush=True)
