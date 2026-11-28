#!/usr/bin/env python3
"""Read-only preflight and exclusive creation of run approval artifacts."""
from pathlib import Path
import hashlib,json,ast,tarfile,subprocess,datetime
R=Path(__file__).resolve().parent
manifest=json.loads((R/'t17b_manifest.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(R/'t17b_stage.tar.gz')==manifest['archive_sha256']
with tarfile.open(R/'t17b_stage.tar.gz') as tf:
 assert tf.getmembers() and all(m.name=='pack_stage' or m.name.startswith('pack_stage/') for m in tf)
src=R/'pack_stage/periodic_bounce/src'
assert all(sha(src/n)==h for n,h in manifest['variants']['periodic_bounce'].items())
for n in ('worker_native.py','controller_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','stub_native.py'):
 ast.parse((R/n).read_text())
assert 'T17_TEST_NX' in (R/'native_analysis.py').read_text()
assert '512u,256u,66u' in (src/'setup.cpp').read_text()
assert '25ul*Tsteps' in (src/'t17_b_native.inc').read_text()
assert "order=(('bounce','1'),('bounce','2'))" in (R/'worker_native.py').read_text()
assert json.loads((R/'DRY_PASS_BOUNCE.json').read_text())['verified']==['bounce_s1','bounce_s2']
plan=json.loads((R/'SESSION_PLAN.json').read_text())
cap_seconds=12.5*3600/5.4
upper=2*(plan['worst_case_solver_s']+plan['per_case_overhead_s'])+plan['fixed_overhead_s']+180
assert upper<cap_seconds,(upper,cap_seconds)
# No new solver runs are made here; host C++ syntax check uses the sealed project headers.
cmd=['g++','-std=c++17','-fsyntax-only','-I'+str(src/'OpenCL/include'),'-I'+str(src/'X11/include'),str(src/'kernel.cpp')]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
(R/'HOST_SYNTAX.log').open('x').write(' '.join(cmd)+'\nexit='+str(p.returncode)+'\n'+p.stdout+p.stderr)
assert p.returncode==0,(p.returncode,p.stderr[-1000:])
# Exact payload matches the worker path open list; dynamic budget is generated after allocation.
payload=('worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json')
assert all((R/n).is_file() for n in payload if n!='t17b_budget.json')
(R/'PATH_PAYLOAD_MAP.md').open('x').write('PAYLOAD → worker 路径\n'+ '\n'.join(f'{n} → /content/{n}' for n in payload)+ '\n/content/t17b_stage.tar.gz → /content/t17b/pack_stage/periodic_bounce/src/*（验包解压）\n/content/native_analysis.py 与 analyze_longspin.py → worker 导入；/content/stub_native.py 仅离线空跑，不上传生产。\n')
seal={n:sha(R/n) for n in payload if n!='t17b_budget.json'}
(R/'PREFLIGHT.ok').open('x').write(json.dumps(seal,indent=2)+'\n')
(R/'NATIVE_PRODUCER_APPROVED.ok').open('x').write('Real worker dry-run passes; native producer frozen from archived T17-B, bounce-specific source and 512x256x66 dimensions hash verified. This is engineering preflight only.\n')
(R/'EXPERIMENT_CARD.md').open('x').write('# T17 大域反弹组两种子实验卡\n\n① 假设：8H×4H 周期空场反弹组两种子可产出同口径的 DATA_CONTRACT 与每2T窗口，用于后续六例统一判据。\n\n② 唯一配置：反弹组种子1/2，网格 512×256×66，25T 冷启动，V0 最多追加3T，2T统计；相对旧根是大域尺寸、起转与描述窗的复合编排改动。\n\n③ 配置：'+str(R/'t17b_stage.tar.gz')+' sha256 '+manifest['archive_sha256']+'；worker sha256 '+seal['worker_native.py']+'；分析器 sha256 '+seal['native_analysis.py']+'。\n\n④ Colab A100 单控制器，预算上限12.5 CU；任务开始/终态从 allocation_events.log 回填。\n\n⑤ 预写判据：V0 按 v2 §3 最后1T 比较，最多3次延长；每例64层、4块、finite、tau_x>0；逐例 SHA/ACK，窗口描述性不下判词。固定于 11-21 08:33 美东之前的委托；结果栏待实机回填。\n')
print('PREFLIGHT_OK',R,'upper_seconds',upper,'cap_seconds',cap_seconds,'archive',manifest['archive_sha256'])
