from pathlib import Path
import hashlib,json,difflib,datetime
R=Path(__file__).resolve().parent
OLD=R.parent/'run_20261118_092856'
BASE=R.parents[1]/'R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off/src/kernel.cpp'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def repl(file,old,new,count=1):
 p=R/file;s=p.read_text();assert s.count(old)==count,(file,old,s.count(old));p.write_text(s.replace(old,new))
s=BASE.read_text();a='return R( // ##########################';assert s.count(a)==1;s=s.replace(a,'string code=R( // ##########################',1)
a=');} // ############################################################### end of OpenCL C code #####################################################################';assert s.count(a)==1
s=s.replace(a,''');
#ifdef SMAG_CS_013
    const string old_coefficient="0.76421222f*sgs_length_factor*sqrt(Q)/rhon";
    const string new_coefficient="0.4315f*sgs_length_factor*sqrt(Q)/rhon";
    const size_t at=code.find(old_coefficient);
    if(at==string::npos || code.find(old_coefficient,at+1u)!=string::npos) throw std::runtime_error("Smagorinsky coefficient anchor mismatch");
    code.replace(at,old_coefficient.size(),new_coefficient);
#endif
    return code;
} // ############################################################### end of OpenCL C code #####################################################################''',1)
k=R/'kernel_t13b.cpp';k.write_text('#include "defines.hpp"\n'+s)
(R/'kernel_manifest.json').write_text(json.dumps({'base_sha256':sha(BASE),'sha256':sha(k)},indent=2)+'\n')
(R/'kernel.diff').write_text(''.join(difflib.unified_diff(BASE.read_text().splitlines(True),k.read_text().splitlines(True),fromfile='T5/kernel.cpp',tofile='T13b/kernel_t13b.cpp')))
repl('worker.py','SMAG_CS_010','SMAG_CS_013',2)
repl('worker.py','kernel_t13.cpp','kernel_t13b.cpp')
repl('worker.py',"assert sha(kernel)==BASE_KERNEL","assert sha(kernel)==BASE_KERNEL") if False else None
repl('worker.py',"if rc:raise RuntimeError('solver exit '+str(rc))","""# Preserve native time-resolved stability extrema even on a nonzero solver exit.
   monitor=dest/'RESULTS/city_stability.csv'
   if monitor.is_file() and monitor.stat().st_size:
    shutil.copyfile(monitor,o/(case+'_city_stability.csv'));seal(o/(case+'_city_stability.csv'))
   if rc:raise RuntimeError('solver exit '+str(rc))""")
repl('worker.py',"shutil.copyfile(monitor,o/(case+'_city_stability.csv'));seal(o/(case+'_city_stability.csv'))\n   if not cl", "if not (o/(case+'_city_stability.csv')).exists():shutil.copyfile(monitor,o/(case+'_city_stability.csv'));seal(o/(case+'_city_stability.csv'))\n   if not cl")
repl('worker.py',"for case in CASES:\n", "for case in CASES:\n",1) if False else None
repl('controller.py','kernel_t13.cpp','kernel_t13b.cpp')
repl('controller.py',"name='luw-t13-a100-'", "name='luw-t13b-a100-'")
repl('controller.py',"(R/'.t13_run_claim')","(R/'.t13b_run_claim')")
repl('controller.py',"if cut-time.time()<2*2520:raise TimeoutError('remaining CU cannot cover two cases')","if cut-time.time()<2*2520:raise TimeoutError('remaining CU cannot cover two cases')") if False else None
repl('controller.py',"frozen=json.loads((R/'PREFLIGHT.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py'})<=frozen.keys()", "frozen=json.loads((R/'PREFLIGHT.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py','EXPERIMENT_CARD.md'})<=frozen.keys()")
repl('controller.py',"if result in ('done','failed'):","if result in ('done','failed'):") if False else None
repl('injected_dry.py',"out=R/'local_injected_dry_t13_sealed'","out=R/'local_injected_dry_t13b'")
# Unique remote root: old task's log, markers and ACKs cannot collide.
for name in ('controller.py','worker.py','remote_io.py'):
 p=R/name;p.write_text(p.read_text().replace('/t13/','/t13b/').replace("/'t13'","/'t13b'").replace("'t13.log'","'t13b.log'").replace("'t13.launch'","'t13b.launch'"))
# Preserve existing budget name, stage archive and path map relation for upload.
for name in ('controller.py','worker.py','injected_dry.py','remote_io.py'):
 p=R/name;p.write_text(p.read_text().replace('t13_budget.json','t13b_budget.json'))
repl('controller.py',"'kernel_t13b.cpp'","'kernel_t13b.cpp'") if False else None
# The producer writes a parsed CSV with per-step max speed and rho extrema; do not infer absent rho columns.
(R/'PATH_PAYLOAD_MAP.md').write_text('PAYLOAD: stage_t5.tar.gz, archive.json, B2u_reference_points.json, comparison.json, kernel_t13b.cpp, kernel_manifest.json, remote_worker_run2.py, t5_sampling.py, worker.py, remote_io.py, t13b_budget.json. Worker opens exactly these under /content; stage is extracted to /content/t13b/stage and its kernel is replaced by kernel_t13b.cpp; dry stub is local only. Runtime outputs /content/t13b/out are downloaded with full filenames plus .sha256.\n')
(R/'EXPERIMENT_CARD.md').write_text('''# T13b Cs=0.13 实验卡（开机前）
① 假设：在 T5 关闭态仅将 Smagorinsky Cs 从约 0.173 降至 0.13，疏密对比 C 可减小。
② 唯一改动：kernel.cpp 生成的 OpenCL 中 0.76421222f→0.4315f，用 SMAG_CS_013 控制；其余 T5 stage、s101/s102、31,000 步和取样不变。仅后处理增加失败时的 stability CSV 回传。
③ 配置：本根 stage_t5.tar.gz、kernel_t13b.cpp、kernel_manifest.json、worker.py、controller.py；SHA256 见 PREFLIGHT.ok；s101/s102 关闭态点表冻结 SHA 为 6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279 / b284b8075072e0c162773096c4b7ba1547f0dc41517b461058803d16d82b8bcf。
④ Colab A100 单会话 s101 后 s102，仅前支稳定才继续；预算约 8 CU，10 CU 止损、11 CU 封顶。会话与终态待填。
⑤ 判据于 11-18 09:24 写定，见 04_Decisions/R21.4a_T13_Smagorinsky常数对疏密对比_设计与判据_20261118.md。全程无 NaN/监测报警、80 点有限，否则「失稳，不判」；平均 ΔC≤−0.04 且各≤−0.02 判杠杆；两种子 |ΔC|<0.016 判不是杠杆；其余中间。另报 ΔMSE_pat、MAE、三组总比、a_80、剔除 N_close 的 C 和稳定性速度/rho 极值时序。实验前预检及终态待回填。
''')
print('PREPARED',R,sha(k))
