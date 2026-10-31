from pathlib import Path
import shutil,tarfile
b=Path(__file__).resolve().parent;src=b/'stage';dest=b/'stage_fully';assert not dest.exists();shutil.copytree(src,dest)
p=dest/'FluidX3D/src'
def edit(name,old,new):
 f=p/name;s=f.read_text();assert s.count(old)==1,(name,s.count(old));f.write_text(s.replace(old,new))
edit('lbm.cpp','stress_nut_probe = Memory<float>(device, 450ul);','stress_nut_probe = Memory<float>(device, 17820ul);')
f=p/'kernel.cpp';s=f.read_text();start='const int iy=xyz.y==40u ? 0 : (xyz.y==70u ? 1 : (xyz.y==100u ? 2 : (xyz.y==130u ? 3 : (xyz.y==160u ? 4 : -1))));';assert s.count(start)==1;s=s.replace(start,'const int iy=xyz.y>=1u && xyz.y<199u ? (int)xyz.y-1 : -1;').replace('(ix*5+iy)*30+iz','(ix*198+iy)*30+iz');f.write_text(s)
f=p/'setup.cpp';s=f.read_text();assert s.count('std::vector<double> stress_u(450,0.),stress_w(450,0.),stress_uw(450,0.),stress_nut(450,0.);')==1;s=s.replace('std::vector<double> stress_u(450,0.),stress_w(450,0.),stress_uw(450,0.),stress_nut(450,0.);','std::vector<double> stress_u(17820,0.),stress_w(17820,0.),stress_uw(17820,0.),stress_nut(17820,0.);').replace('iy<5','iy<198').replace('y=40u+30u*(uint)iy','y=1u+(uint)iy').replace('(ix*5+iy)*30u','(ix*198+iy)*30u').replace('40+30*iy','1+iy');f.write_text(s)
with tarfile.open(b/'fully_inputs.tar.gz','w:gz') as t:
 t.add(dest/'FluidX3D',arcname='FluidX3D');t.add(dest/'case',arcname='case')
print('staged', (b/'fully_inputs.tar.gz').stat().st_size)
