#!/usr/bin/env python3
"""Stage bounce pair in a new Linux spool and archive; old roots remain read-only."""
from pathlib import Path
import hashlib,json,shutil,time,tarfile,math
B=Path('./24_Urban_Wind_LBM/06_Logs/R21.4a_T17_periodic_ABL')
T=B/'big6v3_periodic_t15_k2_20261121_103455'
O=B/'big6_periodic_bounce_v2_20261121_082930'
name='big6v3_periodic_bounce_'+time.strftime('%Y%m%d_%H%M%S')
R=Path.home()/'luw_tmp'/name; A=B/name
R.mkdir(parents=True,exist_ok=False);A.mkdir(exist_ok=False)
files={'worker_native.py':O,'native_analysis.py':O,'analyze_longspin.py':O,'t17b_manifest.json':O,'t17b_stage.tar.gz':O,
       'controller_hardened.py':T,'remote_B.py':T,'machine.py':T,'assert_T17.py':T,'stub_native.py':T,'run_linux.py':T,'dry_check.py':O}
for n,source in files.items():shutil.copyfile(source/n,R/n)
for n in ['native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','machine.py']:
 assert (O/n).read_bytes()==(T/n).read_bytes(),('unexpected non-group change',n)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((R/'t17b_manifest.json').read_text())
assert sha(R/'t17b_stage.tar.gz')==m['archive_sha256']
with tarfile.open(R/'t17b_stage.tar.gz') as tar:
 members={v.name:v for v in tar.getmembers()}
 for fn,h in m['variants']['periodic_bounce'].items():
  p='pack_stage/periodic_bounce/src/'+fn
  assert hashlib.sha256(tar.extractfile(members[p]).read()).hexdigest()==h,(p,h)
c=(R/'controller_hardened.py').read_text()
assert c.count('CAP=11.5')==1 and c.count("CASES=('t15_s1','t15_s2')")==1
c=c.replace('T17 T15 pair','T17 bounce pair').replace('CAP=11.5','CAP=12.5').replace("CASES=('t15_s1','t15_s2')","CASES=('bounce_s1','bounce_s2')").replace('T17 big6v3 T15 #5cfca225','T17 big6v3 bounce #7eb7cc85')
(R/'controller_hardened.py').write_text(c)
r=(R/'run_linux.py').read_text()
assert "'allocation_events.log'" in r
(R/'run_linux.py').write_text(r)
d=(R/'dry_check.py').read_text().replace('dry_content_bounce_v1','dry_content_bounce_v3').replace('DRY_WORKER_BOUNCE_v1.log','DRY_WORKER_BOUNCE_v3.log').replace('DRY_PASS_BOUNCE.json','DRY_PASS_BOUNCE_v3.json').replace('time.time()+360','time.time()+12.5*3600/5.4-90')
(R/'dry_check.py').write_text(d)
rate=json.loads((O/'SESSION_PLAN.json').read_text())['steps_per_second']['bounce']
steps=17950;worst=30*steps/rate
# Conservative allowance based on prior session plus dedicated transfer/ACK/stop overhead.
per=350;fixed=600; cap=12.5; tariff=5.4
p={'steps_per_T':steps,'steps_per_second':{'bounce':rate},'per_case_overhead_s':per,'fixed_overhead_s':fixed,'worst_case_solver_s':worst,'reference':'domain8H matched A100 observed throughput; same conservative T15 v3 budget model, bounce source frozen from v2','single_session_cap_CU':cap,'CU_per_hour':tariff,'first_case_upper_CU':(worst+per+fixed)*tariff/3600,'two_case_upper_CU':(2*worst+2*per+fixed)*tariff/3600}
assert p['two_case_upper_CU']<cap
(R/'SESSION_PLAN.json').write_text(json.dumps(p,indent=2)+'\n')
(R/'NATIVE_PRODUCER_APPROVED.ok').write_text('Frozen bounce v2 pack_stage, native producer and big6 analysis; SHA validated against manifest.\n')
sealed=['worker_native.py','native_analysis.py','analyze_longspin.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','SESSION_PLAN.json','machine.py']
(R/'PREFLIGHT.ok').write_text(json.dumps({n:sha(R/n) for n in sealed},indent=2)+'\n')
(R/'PATH_PAYLOAD_MAP.md').write_text('Worker opens /content/{worker_native.py,native_analysis.py,analyze_longspin.py,t17b_manifest.json,t17b_stage.tar.gz,t17b_budget.json}; /content/t17b/pack_stage/periodic_bounce/src and bin/FluidX3D. Controller uploads all of these plus remote_B.py and assert_T17.py (worker never invokes assert_T17). Fixture only: stub_native.py.\n')
(R/'EXPERIMENT_CARD.md').write_text('假设：大域 periodic_bounce 两种子可按冻结 v2 第 3 节产生完整有效性与科学判据输入；本单仅交测量，不作组判词。\n唯一改动：相对 T15 v3，物理组别切换 periodic_bounce，源码包复用 bounce v2，网格/起转/分析器保持 512×256×66、25T、big6。\n配置路径与 SHA256：'+str(R/'t17b_manifest.json')+' '+sha(R/'t17b_manifest.json')+'；包 '+sha(R/'t17b_stage.tar.gz')+'。\n作业信息：Colab A100，根 '+str(A)+'，控制器结束后回填。\n判据写定时间：v2 第 3 节 11-19；V0–V3、S2/S2b/S3 不改；由 Lead 六例齐全后判。\n')
# Do not copy result-like evidence until dry worker has actually passed.
print(json.dumps({'linux_spool':str(R),'archive':str(A),'plan':p,'payload_sha256':{n:sha(R/n) for n in sealed}},ensure_ascii=False))
