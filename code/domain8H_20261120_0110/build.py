#!/usr/bin/env python3
"""Create independent 8H x 4H diagnostic from frozen 30T package."""
import hashlib,json,pathlib,shutil,tarfile,difflib
R=pathlib.Path(__file__).resolve().parent
OLD=R.parent/'longspin_20261120_002118_v3'
assert not (R/'pack_stage').exists()
shutil.copytree(OLD/'pack_stage',R/'pack_stage')
for n in ['worker_longspin.py','analyze_longspin.py','remote_longspin.py','stub_longspin.py','machine.py','controller_longspin.py','dry_run.py']:
 shutil.copy2(OLD/n,R/n)
def change(path, substitutions):
 s=path.read_text();orig=s
 for old,new in substitutions:
  assert s.count(old)>=1,(path,old,s.count(old));s=s.replace(old,new)
 path.write_text(s)
 (R/(path.name+'.diff')).write_text(''.join(difflib.unified_diff(orig.splitlines(True),s.splitlines(True),fromfile=str(OLD/path.relative_to(R)),tofile=str(path))))
SRC=R/'pack_stage/periodic_t15_k2/src'
change(SRC/'setup.cpp',[('LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice);','LBM lbm(512u,256u,66u,units.nu(1.48e-5f),f_lattice);')])
# kx=ky=2pi/32 and phase in metres: exact periodic replication of the old physical-coordinate field.
INC=SRC/'t17_b_native.inc'
change(INC,[('const ulong total=30ul*Tsteps;','const ulong total=22ul*Tsteps;'),('for(ulong w=1ul;w<=15ul;++w) {','for(ulong w=1ul;w<=11ul;++w) {'),('const ulong target=(w==15ul)?total:w*window;','const ulong target=(w==11ul)?total:w*window;'),('std::to_string(w)+"/15 step "','std::to_string(w)+"/11 step "')])
change(R/'analyze_longspin.py',[('NX,NY,AREA=256,128,256*128','NX,NY,AREA=512,256,512*256'),('30*T);duration=hi-lo','22*T);duration=hi-lo'),('range(0,NX//2+1,8)','range(0,NX//2+1,16)'),('range(0,NY//2+1,8)','range(0,NY//2+1,16)')])
# prior analyzer uses w>=14 in main, not the alternate spelling
p=R/'analyze_longspin.py';s=p.read_text();assert 'analyze(d,w,w>=14)' in s;p.write_text(s.replace('analyze(d,w,w>=14)','analyze(d,w,w>=10)'))
change(R/'worker_longspin.py',[('while proc.poll() is None or len(delivered)<15:','while proc.poll() is None or len(delivered)<11:'),('range(1,16)','range(1,12)'),('if len(delivered)==15:break','if len(delivered)==11:break'),("{'windows':15,'ack':True}","{'windows':11,'ack':True}")])
change(R/'controller_longspin.py',[("done['windows']==15", "done['windows']==11"),('range(1,16)', 'range(1,12)'),('cap=2.0','cap=4.0'),('30*T/600;fixed=110','22*T/240;fixed=260'),("'--max-hours','2','--expect-hours','2'","'--max-hours','4','--expect-hours','4'")])
# Increased domain fixture: 11 windows, correct frame geometry and small synthetic T.
change(R/'stub_longspin.py',[('end=30*T;area=256*128','end=22*T;area=512*256'),('78,32768,200,longspin','78,131072,200,longspin'),('size=(2,128,256,3)','size=(2,256,512,3)'),('range(1,16)','range(1,12)'),('30T 15 WINDOWS','22T 11 WINDOWS')])
change(R/'dry_run.py',[('len(hashes)==19','len(hashes)==15'),('range(1,16)','range(1,12)'),('==15','==11'),('15 windows, 19 files','11 windows, 15 files'),("'PREFLIGHT_LONGSPIN.ok'","'PREFLIGHT_LONGSPIN.ok'")])
# seal source tar and manifest
arc=R/'longspin_stage.tar.gz'
with tarfile.open(arc,'w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files={n:sha(SRC/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')}
(R/'longspin_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'source_files':files},indent=2)+'\n')
(R/'EXPERIMENT_CARD.md').write_text('① 假设：扩大周期域后，T15 s1 平衡近地指标的域敏感性可由 22T 试验测量。\n② 唯一改动：水平域 256×128 → 512×256 格；初始扰动波长及相位按物理坐标保持 32 m 周期，z/H、F、种子、dt、壁模型不变。\n③ 配置：longspin_stage.tar.gz sha256 '+sha(arc)+'；longspin_manifest.json sha256 '+sha(R/'longspin_manifest.json')+'。\n④ 作业：Colab A100，尚未分配；运行根 '+str(R)+'。\n⑤ 判据：本轮仅报告窗口、曲线和相对小域的数值差，不判域敏感性；写定时间 11-20 01:10 EST。\n')
print('BUILT',arc,sha(arc),files)
