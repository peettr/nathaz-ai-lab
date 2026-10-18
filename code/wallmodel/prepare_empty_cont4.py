"""Stage an immutable continuation archive; never alter prior runs."""
from pathlib import Path
import tarfile, tempfile, shutil, re, struct, os
root=Path(__file__).resolve().parent
old=root/'luw_wall_empty_inputs_r13.tar.gz'
new=root/'empty_cont4_inputs.tar.gz'
assert old.exists() and not new.exists()
source=root/'LatticeUrbanWind_repo/core/cfd_core/FluidX3D'
with tempfile.TemporaryDirectory(dir=root) as tmp:
    tmp=Path(tmp)
    with tarfile.open(old) as tar: tar.extractall(tmp,filter='data')
    solver=tmp/'FluidX3D'
    for name in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'):
        shutil.copy2(source/'src'/name,solver/'src'/name)
    conf=tmp/'example_ProfileResearch_noDEM/conf.luwpf'
    text=conf.read_text()
    assert 'vk_inlet_ti' not in text
    text+='\nvk_inlet_enable = true\nvk_inlet_ti = 0.1621\nvk_inlet_l = 100\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
    text=text.replace('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 200.000000]')
    assert 'si_y_cfd = [0.000000, 200.000000]' in text
    conf.write_text(text)
    stl=tmp/'example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl'
    b=stl.read_bytes();n=struct.unpack_from('<I',b,80)[0];assert n==9210
    tri=bytearray(b[84+(n-12)*50:]);assert len(tri)==600
    for i in range(12):
        for j in range(3):
            for axis,oldval,newval in ((0,2022.5001,500.),(1,1996.5001,200.)):
                off=i*50+12+j*12+axis*4
                v=struct.unpack_from('<f',tri,off)[0]
                assert min(abs(v),abs(v-oldval))<.02,(i,j,axis,v)
                struct.pack_into('<f',tri,off,0. if abs(v)<.02 else newval)
    stl.write_bytes(b[:80]+struct.pack('<I',12)+tri)
    with tarfile.open(new,'w:gz') as tar:
        for child in tmp.iterdir():tar.add(child,arcname=child.name)
print(new,new.stat().st_size)
