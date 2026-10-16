"""Build immutable, minimal LUW CRC deployment from existing Git checkout."""
from pathlib import Path
import shutil, struct, numpy as np, subprocess, sys
src=Path('./.cache/dwt-luw-eval')
commit=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
assert commit=='dd438c1c68664980a92460e4778f18f36be3f47c',commit
root=Path(sys.argv[1]);assert not root.exists(),root
root.mkdir(parents=True)
shutil.copytree(src/'core/cfd_core/FluidX3D',root/'FluidX3D',ignore=shutil.ignore_patterns('temp','bin'))
base=src/'examples/example_ProfileResearch_noDEM';case=root/'case_west'
(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:
 shutil.copy2(base/rel,case/rel)
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]);p=case/'proj_temp/CaseE_PF.stl';a=np.fromfile(p,dtype=D,offset=84).copy();assert len(a)==9210
x0,x1,y0,y1=300.,1500.,650.,1350.;v=a['v'];assert np.all((v[:-12,:,0]>x0)&(v[:-12,:,0]<x1)&(v[:-12,:,1]>y0)&(v[:-12,:,1]<y1))
v[:,:,0]-=x0;v[:,:,1]-=y0
for component,old_low,old_high,span in [(0,-x0,2022.5001-x0,x1-x0),(1,-y0,1996.5001-y0,y1-y0)]:
 z=v[-12:,:,component];z[np.isclose(z,old_low,atol=.01)]=0;z[np.isclose(z,old_high,atol=.01)]=span
assert np.allclose(v[-12:].min(axis=(0,1))[:2],[0,0]) and np.allclose(v[-12:].max(axis=(0,1))[:2],[1200,700])
with p.open('wb') as f:
 f.write(b'LUW Case E cropped box CRC'.ljust(80,b' '));f.write(struct.pack('<I',len(a)));a.tofile(f)
c=case/'conf.luwpf';txt=c.read_text()
for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1200.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 700.000000]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
 assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
assert 'n_gpu = [2, 1, 1]' in txt
c.write_text(txt+'\nrun_nstep = 30000\npurge_avg = 25000\npurge_avg_stride = 40\noutput_tke_ti_tls = []\n')
(root/'source_commit.txt').write_text(commit+'\n')
print('STAGED',root,commit,'triangles',len(a),'configuration:\n',c.read_text())
