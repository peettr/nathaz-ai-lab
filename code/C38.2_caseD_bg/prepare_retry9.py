#!/usr/bin/env python3
"""Prepare immutable retry9 controller from retry8; do not touch retry8."""
from pathlib import Path
import datetime, shutil, hashlib, json, tarfile
base=Path(__file__).resolve().parent
source=base/'CaseD_retry8_20261115_0730'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M')
dest=base/f'CaseD_retry9_{stamp}'
dest.mkdir(exist_ok=False)
for name in ('controller.py','remote_caseD.py','launch.py','check.py','gpu_probe.py','diagnostic_extract.py','verify_source.py','cased_stage.tar.gz','SOURCE.txt'):
    shutil.copy2(source/name,dest/name)
shutil.copytree(source/'source_parts',dest/'source_parts')
for name in ('controller.py','remote_caseD.py','launch.py','check.py'):
    p=dest/name
    s=p.read_text().replace('luw-c38-cased-r8-20261115','luw-c38-cased-r9-20261115')
    if name=='controller.py':
        s=s.replace("for gpu in ('A100',):", "for gpu in ('A100','G4','L4','H100'):")
        s=s.replace("NAME='luw-c38-cased-r9-20261115'", "NAME='luw-c38-cased-r9-20261115'")
        s=s.replace("rate=6.81;deadline=None", "rate=6.81;deadline=None;gpu_selected=None")
        s=s.replace('global created,start,rate,deadline', 'global created,start,rate,deadline,gpu_selected')
        s=s.replace("created=True;rate=max(rate,{'A100':6.81,'H100':14.0,'G4':8.0,'L4':6.81}[gpu]);record('gpu_allocated',gpu=gpu,conservative_rate=rate);break", "created=True;gpu_selected=gpu;rate=max(rate,{'A100':6.81,'H100':14.0,'G4':8.0,'L4':6.81}[gpu]);record('gpu_allocated',gpu=gpu,conservative_rate=rate);break")
        s=s.replace("if not any(token in str(exc) for token in ('Service Unavailable','Precondition Failed','Allocation refused')):raise", "if not any(token in str(exc) for token in ('Service Unavailable','Precondition Failed','Allocation refused','Backend rejected accelerator')):raise")
        s=s.replace("record('allocation_refused',gpu=gpu,error=str(exc)[-500:]);continue", "record('allocation_refused',gpu=gpu,error=str(exc)[-500:]);continue")
        s=s.replace("assert 'MEMCHECK' in probe and 'FREE_G' in probe", "assert 'MEMCHECK' in probe and 'FREE_G' in probe")
        s=s.replace("record('memory_probe_pass',detail=probe[-1200:])", "record('memory_probe_pass',gpu=gpu_selected,detail=probe[-1200:])")
        s=s.replace('ensure_time(2350)', 'ensure_time(700)')
        s=s.replace("record('verified',result_path=str(p)","record('verified',gpu=gpu_selected,result_path=str(p)")
        s=s.replace("record('session_stopped',sessions=", "record('session_stopped',gpu=gpu_selected,sessions=")
        s=s.replace("'--expect-hours','1.5','--max-hours','2'", "'--expect-hours','1.5','--max-hours','2'")
    elif name=='remote_caseD.py':
        old="assert remaining>=2250, f'budget insufficient for solver+extraction+stop: {remaining:.1f}s'"
        new="""assert remaining>=700, f'budget insufficient for calibration+stop: {remaining:.1f}s'
 # Same full geometry and physics, but 1000-step calibration in a fresh subroot.
 # Includes real startup and average-field overhead; retain only as a throughput probe.
 cal_dir=R/'calibration_1000';shutil.copytree(C,cal_dir,ignore=shutil.ignore_patterns('RESULTS'))
 cal=(cal_dir/'conf.luwpf').read_text().replace('run_nstep = 33767','run_nstep = 1000').replace('purge_avg = 23215','purge_avg = 1')
 assert cal!=(cal_dir/'conf.luwpf').read_text()
 (cal_dir/'conf.luwpf').write_text(cal)
 tcal=time.monotonic()
 cp=subprocess.Popen([str(binary),str(cal_dir/'conf.luwpf')],cwd=cal_dir,stdin=subprocess.DEVNULL,stdout=(R/'calibration_solver.log').open('w'),stderr=subprocess.STDOUT)
 try: calret=cp.wait(timeout=max(1,deadline-time.time()-320))
 except subprocess.TimeoutExpired:
  cp.terminate();cp.wait(timeout=20);raise RuntimeError('calibration hit CU deadline')
 cal_elapsed=time.monotonic()-tcal
 (E/'calibration_1000.json').write_text(json.dumps({'steps':1000,'exit':calret,'wall_seconds':cal_elapsed,'timestamp':time.time()},indent=2))
 log('CALIBRATION_1000',calret,cal_elapsed)
 assert calret==0,'1000-step calibration failed; full solve not started'
 # Conservative: 20% overhead on the measured per-step rate and fixed time for
 # extraction/download/stop; refuse before spending on a run predicted >5 CU.
 predicted_s=cal_elapsed*33767/1000*1.2+300
 remaining=deadline-time.time()
 log('PREDICTED_FULL_SOLVE_SECONDS',round(predicted_s,1),'REMAINING_SECONDS',round(remaining,1))
 assert predicted_s<=remaining, f'5 CU predicted exceedance: full solve+export {predicted_s:.1f}s > remaining {remaining:.1f}s'"""
        assert old in s
        s=s.replace(old,new)
        s=s.replace("'solver_exit.json','pointvalues.json',*diagnostic_hashes", "'solver_exit.json','calibration_1000.json','pointvalues.json',*diagnostic_hashes")
    p.write_text(s)
# Accept advertised 24 GB board where CUDA reports 23034 MiB; insist on actual free
# memory (>15 GiB) separately. G4/L4 devices vary; data wins over model name.
p=dest/'gpu_probe.py';s=p.read_text().replace('int(total)>=24*1024','int(total)>=23000');p.write_text(s)
card=(dest/'EXPERIMENT_CARD.md')
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
card.write_text(f'''# Case D retry9 — frozen before GPU request ({datetime.datetime.now():%m-%d %H:%M} EST)\n\n① Hypothesis: measured inlet/open-ground/street means may discriminate sources of retry6 low bias; no presumed cause.\n② Same retry6 configuration/geometry/statistical window (33767, 23215, stride 42). Retry8 timeout-safe controller; one A100 request then authorized >=24 GB alternatives. Full-size 1000-step calibration measures machine throughput before full solve. BG paused.\n③ Immutable deck SHA256 {sha(dest/'cased_stage.tar.gz')}; source archive SHA256 88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0; controller SHA256 {sha(dest/'controller.py')}; worker SHA256 {sha(dest/'remote_caseD.py')}; diagnostics SHA256 {sha(dest/'diagnostic_extract.py')}. Root {dest}.\n④ GPU allocation and session interval to be filled after run; creation-to-stop budget <5 CU (estimated, not invoice).\n⑤ Fixed now: native fluid-mask geometry gate before full solve; 1000-step measured rate times 33767 with 20% margin and 300 s export/stop reserve must fit remaining 4.96-CU session budget, else no full solve. On success retain 99 points, actual mean inlet/open/street profiles and 1/2/3/5/10 m planes, VTK SHA/header, per-file hashes, three actual-field ratios. Unavailable outputs marked unmeasured, no surrogate.\n''')
print(dest)
print('controller_sha256',sha(dest/'controller.py'),'worker_sha256',sha(dest/'remote_caseD.py'))
