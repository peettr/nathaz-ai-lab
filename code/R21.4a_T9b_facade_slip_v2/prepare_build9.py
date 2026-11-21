#!/usr/bin/env python3
"""Freeze build9 without modifying historical source or evidence."""
from pathlib import Path
import shutil,hashlib,difflib,tarfile,json,re,datetime
P=Path(__file__).resolve().parent
B=P/'build6_20261117_123412'; E=P/'build8_20261117_1320'
R=P/('build9_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
R.mkdir(exist_ok=False)
V=R/'FluidX3D_facade_v9';shutil.copytree(B/'FluidX3D_facade_v6',V)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
# Remove all test-counter conditional blocks. All 16 mirror loads stay byte-for-byte.
for p in (V/'src').rglob('*'):
 if not p.is_file() or p.suffix not in ('.cpp','.hpp'):continue
 s=p.read_text();before=s
 if p.name=='setup.cpp':
  s,n=re.subn(r'^[ \t]*#ifdef FACADE_COUNT\n[ \t]*<<\(step\?count\[0\]:0u\)\n[ \t]*#else\n[ \t]*<<0u\n[ \t]*#endif\n','',s,flags=re.M)
  assert n==1,n
 s,n=re.subn(r'^[ \t]*#ifdef FACADE_COUNT\n.*?^[ \t]*#endif\n','',s,flags=re.M|re.S)
 if p.name=='kernel.cpp':
  assert n==16,n
  fragment=')+"#ifdef FACADE_COUNT"+R(\n    , global uint* facade_link_count\n)+"#endif"+R(\n)'
  assert s.count(fragment)==1;s=s.replace(fragment,'')
 if p.name=='setup.cpp':
  assert n==2,n
  s=s.replace('tangent_momentum,device_mirror_links\\n','tangent_momentum\\n')
  old="<<faces<<','<<px<<','\n                 <<'\\n';"
  assert old in s;s=s.replace(old,"<<faces<<','<<px<<'\\n';")
 if p.name=='lbm.cpp':assert n==2,n
 if p.name=='lbm.hpp':assert n==1,n
 if s!=before:p.write_text(s)
assert not any('FACADE_COUNT' in p.read_text() or 'facade_link_count' in p.read_text() for p in (V/'src').rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp'))
assert 'atomic_inc' not in (V/'src/kernel.cpp').read_text()
# source-derived mirror path: strip only counter fragments in parent and compare entire kernel.
a=(B/'FluidX3D_facade_v6/src/kernel.cpp').read_text();b=(V/'src/kernel.cpp').read_text()
a=re.sub(r'^[ \t]*#ifdef FACADE_COUNT\n.*?^[ \t]*#endif\n','',a,flags=re.M|re.S)
a=a.replace(')+"#ifdef FACADE_COUNT"+R(\n    , global uint* facade_link_count\n)+"#endif"+R(\n)','')
assert a==b
(R/'mirror_path_byte_identity.json').write_text(json.dumps({'v6_kernel_after_removing_counter_exactly_equals_v9_kernel':True,'v9_kernel_sha256':sha(V/'src/kernel.cpp'),'counter_removed_from_v6_only':True},indent=2)+'\n')
changes=[]
for p in V.rglob('*'):
 if not p.is_file():continue
 old=B/'FluidX3D_facade_v6'/p.relative_to(V)
 if old.is_file() and old.read_bytes()!=p.read_bytes():
  changes+=list(difflib.unified_diff(old.read_text().splitlines(keepends=True),p.read_text().splitlines(keepends=True),fromfile='v6/'+str(p.relative_to(V)),tofile='v9/'+str(p.relative_to(V))))
(R/'diff_vs_v6.patch').write_text(''.join(changes))
for n in ('controller_gate.py','worker_gate.py','launch_gate.py','probe_gate.py'):
 s=(E/n).read_text().replace('t9b8','t9b9').replace('build8','build9').replace('facade_v8','facade_v9').replace('luw-t9b8-g4-1117-a1','luw-t9b9-g4-1117-a1')
 (R/n).write_text(s)
(R/'EXPERIMENT_CARD.md').write_text('# T9b build9 experiment card\n\n假设：无计数代码的 v6 镜面可在 GPU 上由切向动量保留证明激活。\n唯一改动：删除 FACADE_COUNT 诊断，镜面读写逐字不变；关闭态原生反弹。\n配置路径及 SHA256：见 t9b9_manifest.json；本卡在运行前冻结。\n作业信息：Colab G4，≤4 CU；会话创建与终止后填。\n判据写定时间：11-17 13:18 EST；x/y 开支相对变化≤1e-5，关支末值≤初值0.9，开关 trace SHA 不同；任何不过即停。立方体仅另报；城市门控按委托执行。\n')
arc=R/'t9b9_source.tar.gz'
with tarfile.open(arc,'w:gz') as t:t.add(V,arcname=V.name)
members={str(p.relative_to(V)):sha(p) for p in V.rglob('*') if p.is_file()}
(R/'t9b9_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'members':members},indent=2)+'\n')
print(R,sha(arc),len(members),'diff lines',len(changes))
