"""Prepare two empty 500x64x270 Case-E-profile runs, preserving untouched LUW binary separately."""
from pathlib import Path
import tarfile,subprocess,shutil,struct,time
r=Path('/content/luw_wall_empty_r13');r.mkdir(exist_ok=False)
archive=Path('/content/luw_wall_empty_inputs_r13.tar.gz')
with tarfile.open(archive) as tar:tar.extractall(r,filter='data')
base=r/'FluidX3D';ex=r/'example_ProfileResearch_noDEM'
for variant in ('off','on'):
 source=r/('solver_'+variant);shutil.copytree(base,source)
 defines=source/'src/defines.hpp'
 if variant=='on':
  text=defines.read_text();assert text.count('//#define GROUND_WALL_MODEL')==1;defines.write_text(text.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL'))
 start=time.monotonic()
 with (r/f'build_{variant}.log').open('w') as out:cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=300)
 print('BUILD',variant,cp.returncode,'wall_s',round(time.monotonic()-start,1),flush=True);assert cp.returncode==0
 case=r/('case_'+variant);(case/'proj_temp').mkdir(parents=True);(case/'wind_bc').mkdir()
 shutil.copy2(ex/'wind_bc/profile.dat',case/'wind_bc/profile.dat');shutil.copy2(ex/'conf.luwpf',case/'conf.luwpf')
 stl=(ex/'proj_temp/CaseE_PF.stl').read_bytes();n=struct.unpack_from('<I',stl,80)[0];assert n==9210
 tri=bytearray(stl[84+(n-12)*50:]);assert len(tri)==12*50
 # Preserve only the 12 outer-base facets; reset flat plate extents from legacy 2km to 500x64m.
 bounds=((2022.5001,500.0),(1996.5001,64.0))
 for i in range(12):
  for j in range(3):
   for axis,(old,span) in enumerate(bounds):
    offset=i*50+12+j*12+axis*4;value=struct.unpack_from('<f',tri,offset)[0]
    assert min(abs(value),abs(value-old))<.02,(i,j,axis,value)
    struct.pack_into('<f',tri,offset,0. if abs(value)<.02 else span)
 (case/'proj_temp/CaseE_PF.stl').write_bytes(stl[:80]+struct.pack('<I',12)+tri)
 c=case/'conf.luwpf';txt=c.read_text()
 for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 64.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
  assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
 txt+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\n'
 c.write_text(txt)
 print('CASE',variant,'empty_triangles=12','dx=1','domain=500x64x270','steps=31000',flush=True)
print('BOOTSTRAP_DONE',flush=True)
