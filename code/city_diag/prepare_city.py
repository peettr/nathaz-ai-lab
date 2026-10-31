"""Stage two isolated Case E input archives; no solver execution on 工作站."""
from pathlib import Path
import shutil, struct, tarfile, hashlib
R=Path(__file__).resolve().parent
BASE=R.parent/'stress_budget/stage_mixing07'
ORIG=Path('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl')
assert ORIG.is_file()
raw=ORIG.read_bytes(); n=struct.unpack_from('<I',raw,80)[0]
assert n==9210 and len(raw)==84+50*n
# Identical crop as r10 bootstrap: translate every triangle then clip 12 base triangles.
from array import array
import sys
assert sys.byteorder=='little'
a=bytearray(raw);a[:80]=b'LUW Case E official-size base r5'.ljust(80,b' ')
for j in range(n):
 for vertex in range(3):
  for component,low,high,span in [(0,760.,2022.5001-760.,500.),(1,750.,1996.5001-750.,500.)]:
   off=84+50*j+12+vertex*12+component*4
   val=struct.unpack_from('<f',raw,off)[0]-low
   if j>=n-12:
    if abs(val+low)<.01:val=0.
    elif abs(val-high)<.01:val=span
   struct.pack_into('<f',a,off,val)
for tag,alpha in [('mix07','0.70f'),('mix10','1.0f')]:
 dst=R/('stage_'+tag)
 assert not dst.exists(),dst
 shutil.copytree(BASE/'FluidX3D',dst/'FluidX3D',ignore=shutil.ignore_patterns('bin','obj','.git','__pycache__'))
 (dst/'case/proj_temp').mkdir(parents=True)
 shutil.copytree(BASE/'case/wind_bc',dst/'case/wind_bc')
 (dst/'case/proj_temp/CaseE_PF.stl').write_bytes(a)
 conf=(BASE/'case/conf.luwpf').read_text().replace('si_y_cfd = [0.000000, 200.000000]','si_y_cfd = [0.000000, 500.000000]')
 assert 'si_y_cfd = [0.000000, 500.000000]' in conf
 (dst/'case/conf.luwpf').write_text(conf)
 kp=dst/'FluidX3D/src/kernel.cpp';text=kp.read_text()
 old='0.70f*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)'
 assert text.count(old)==1
 kp.write_text(text.replace(old,alpha+'*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)'))
 tar=R/(tag+'_inputs.tar.gz')
 with tarfile.open(tar,'w:gz') as t:
  t.add(dst/'FluidX3D',arcname='FluidX3D');t.add(dst/'case',arcname='case')
 print(tag,tar.stat().st_size,hashlib.sha256(tar.read_bytes()).hexdigest())
