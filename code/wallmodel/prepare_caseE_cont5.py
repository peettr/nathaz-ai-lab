"""Stage Case E R10a geometry and inputs without touching the baseline."""
from pathlib import Path
import struct,tarfile,tempfile,shutil
r=Path(__file__).resolve().parent;out=r/'caseE_cont5_inputs.tar.gz';assert not out.exists()
repo=r/'LatticeUrbanWind_repo';base=repo/'examples/example_ProfileResearch_noDEM'
with tempfile.TemporaryDirectory(dir=r) as d:
 d=Path(d);shutil.copytree(repo/'core/cfd_core/FluidX3D',d/'FluidX3D',ignore=shutil.ignore_patterns('bin','*.o'))
 case=d/'case';(case/'wind_bc').mkdir(parents=True);(case/'proj_temp').mkdir()
 for name in ('conf.luwpf','wind_bc/profile.dat'):shutil.copy2(base/name,case/name)
 source=base/'proj_temp/CaseE_PF.stl';b=source.read_bytes();n=struct.unpack_from('<I',b,80)[0];assert n==9210
 a=bytearray(b[84:]);assert len(a)==n*50
 for i in range(n):
  for j in range(3):
   for axis,shift,span,original_span in ((0,760.,500.,2022.5001),(1,750.,500.,1996.5001)):
    o=i*50+12+j*12+axis*4;v=struct.unpack_from('<f',a,o)[0];v-=shift
    if i>=n-12:
     if abs(v+shift)<.02:v=0.
     elif abs(v-(original_span-shift))<.02:v=span
     else:raise ValueError((i,j,axis,v))
    else:assert 0<v<span,(i,j,axis,v)
    struct.pack_into('<f',a,o,v)
 (case/'proj_temp/CaseE_PF.stl').write_bytes(b'LUW Case E internal wall diagnostic'.ljust(80,b' ')+struct.pack('<I',n)+a)
 conf=case/'conf.luwpf';txt=conf.read_text()
 for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 500.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
  assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
 txt+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\nvk_inlet_ti = 0.1621087892\nvk_inlet_l = 100.0\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
 conf.write_text(txt)
 with tarfile.open(out,'w:gz') as t:
  for p in d.iterdir():t.add(p,arcname=p.name)
print(out,out.stat().st_size)
