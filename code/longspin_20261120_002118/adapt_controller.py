#!/usr/bin/env python3
"""Adapt tested B controller's retry/ownership/stop logic for one 30T diagnostic."""
import pathlib
r=pathlib.Path(__file__).resolve().parent
s=(r/'controller_native.py').read_text()
s=s.replace("ALL_CASES=tuple(g+'_s'+s for g in ('bounce','t4','t15') for s in ('1','2'))","ALL_CASES=('longspin',)")
s=s.replace("PAYLOAD=('worker_native.py','native_analysis.py','remote_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json')","PAYLOAD=('worker_longspin.py','analyze_longspin.py','remote_longspin.py','longspin_stage.tar.gz','longspin_manifest.json','longspin_budget.json')")
s=s.replace("cases=('t15_s1','t15_s2','t4_s1','t4_s2','bounce_s1','bounce_s2')","cases=('longspin',)")
s=s.replace("mode='production'","mode='longspin'").replace("if mode not in ('smoke','production')","if mode!='longspin'")
s=s.replace('t17b','longspin').replace('T17 B ','T17 longspin ')
s=s.replace('remote_B as io','remote_longspin as io')
s=s.replace("cap=3.5","cap=2.0").replace("-90;hard=","-120;hard=")
s=s.replace("  while time.time()<cut:\n","  while time.time()<cut:\n")
start=s.index('    if len(acks)<len(cases):')
end=s.index("    if 'run.failed'",start)
s=s[:start]+'''    if not acks and 'handoff.json' in verified:
     hashes=json.loads((o/'handoff.json').read_text())['sha256']
     if set(hashes)<=set(verified) and all(verified[k]==v for k,v in hashes.items()):
      ack('longspin',hashes);acks.append('longspin');print('ACK longspin',flush=True)
'''+s[end:]
s=s.replace("done['verified']==list(cases) and acks==list(cases) and all(x+'_case.json' in verified for x in cases)","done['windows']==15 and done['ack'] and acks==['longspin'] and all('window_%02d.json'%w in verified for w in range(1,16))")
start=s.index('  plan=json.loads(')
end=s.index("  for n in PAYLOAD:",start)
s=s[:start]+'''  # Worst-case cold start: 30T at a conservative 400 steps/s plus 500 s
  # compilation/transfer/analysis reserve, 120 s teardown. Recheck after upload.
  T=17950.3769;worst_solver=30*T/400;fixed=200
  budget=d/'longspin_budget.json';budget.write_text(json.dumps({'mode':mode,'work_deadline':cut,'teardown_s':120})+'\\n')
'''+s[end:]
s=s.replace("required=(2000/plan['steps_per_second']['t15']+90) if mode=='smoke' else plan['worst_case_solver_s']+plan['fixed_overhead_s']","required=worst_solver+fixed+120")
s=s.replace("if not (R/'NATIVE_PRODUCER_APPROVED.ok').is_file():raise RuntimeError('native producer preflight required')","if not (R/'PREFLIGHT_LONGSPIN.ok').is_file():raise RuntimeError('diagnostic dry run required')")
s=s.replace("'--max-hours','1','--expect-hours','1'","'--max-hours','2','--expect-hours','2'")
s=s.replace("'--pull','/content/longspin.log:'+str(d/'worker_progress.log')","'--pull','/content/longspin.log:'+str(d/'worker_progress.log'),'--pull','/content/longspin/out/window_*.json:'+str(d/'checkpoint')")
s=s.replace("'--final-pull','/content/longspin/out/*.json:'+str(d/'final')","'--final-pull','/content/longspin/out/*.json:'+str(d/'final')")
(r/'controller_longspin.py').write_text(s)
io=(r/'remote_B.py').read_text().replace('t17b','longspin').replace("LABELS=tuple(g+'_s'+s for g in ('bounce','t4','t15') for s in ('1','2'))","LABELS=('longspin',)")
io=io.replace("if json.loads((c/'longspin_budget.json').read_text())['mode'] not in ('production','smoke')","if json.loads((c/'longspin_budget.json').read_text())['mode']!='longspin'").replace("c/'worker_native.py'","c/'worker_longspin.py'")
(r/'remote_longspin.py').write_text(io)
print('controller and remote generated')
