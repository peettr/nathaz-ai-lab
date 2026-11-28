from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'worker_native.py').read_text()
s=s.replace("GROUPS=('t15',);SEEDS=('1','2')","GROUPS=('K1a','K1b','K2','K3a','K3b');SEEDS=('1',)")
s=s.replace("for group in (('t15',) if mode=='smoke' else GROUPS):","for group in ('B0',)+GROUPS:")
s=s.replace("order=(('t15','1'),('t15','2'))","order=tuple((g,'1') for g in (('K1a','K1b','K2','K3a','K3b') if c0_pass else ('K1a','K1b','K2')))")
anchor='''  cases={g:{} for g in GROUPS}
'''
assert s.count(anchor)==1
smoke='''  # C-0 uses the already native-compiled K3a, then applies the frozen rho gate.
  c0=OUT/'C0_K3a';c0.mkdir()
  c0_env={**os.environ,'T17_B_MODE':'smoke','T17_B_DIR':str(c0),
          'T17_B_SEED':'1','T17_STAGE_A_ALLOW':'1',
          'LD_LIBRARY_PATH':str(exes['K3a'][1]/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  c0_log=OUT/'C0_K3a_solver.log'
  c0_pass=False
  with c0_log.open('x') as out:
   proc=subprocess.Popen([str(exes['K3a'][0])],cwd=exes['K3a'][1],env=c0_env,
                         stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
   while proc.poll() is None:
    if time.time()>=deadline-budget['teardown_s']:
     proc.terminate();raise TimeoutError('C0 deadline')
    time.sleep(.1 if budget.get('fixture') else 2)
   c0_pass=(proc.returncode==0 and (c0/'producer.done').is_file())
  seal(c0_log)
  monitor=c0/'rho_monitor.csv'
  if not budget.get('fixture') and c0_pass:
   import math
   lines=monitor.read_text().splitlines() if monitor.exists() else []
   expected=list(range(1000,53001,1000))+[53851]
   rows=[line.split(',') for line in lines]
   c0_pass=(len(rows)==len(expected) and [int(x[0]) for x in rows]==expected
     and all(len(x)==3 and all(math.isfinite(float(y)) for y in x[1:])
        and .9<=float(x[1])<=float(x[2])<=1.1 for x in rows))
  result={'pass':c0_pass,'steps':53851 if c0_pass else None,
          'rho_range':([min(float(x[1]) for x in rows),max(float(x[2]) for x in rows)]
             if not budget.get('fixture') and monitor.exists() and rows else None),
          'solver_rc':proc.returncode,'fixture_only':bool(budget.get('fixture'))}
  verdict=OUT/'C0_verdict.json';verdict.write_text(json.dumps(result)+'\\n');seal(verdict)
  if monitor.exists():
   dest=OUT/'C0_rho_monitor.csv';shutil.copyfile(monitor,dest);seal(dest)
  print('C0_VERDICT',result,flush=True)
  cases={g:{} for g in GROUPS}
'''
s=s.replace(anchor,smoke)
s=s.replace("budget['steps_per_second'][group]","budget['steps_per_second'][group]")
s=s.replace("   if idx: rate=min(rate,budget['steps_per_T']*30/max(time.time()-case_start,1))","   if idx: rate=min(rate,budget['steps_per_T']*30/max(time.time()-case_start,1))")
s=s.replace("'budget_stop':len(verified_cases)<len(order)","'budget_stop':len(verified_cases)<len(order),'c0_pass':c0_pass,'expected':list(label+'_s1' for label,_ in order)")
# Establish non-physical fixture only: K3a stub smoke must not claim scientific success.
s=s.replace("  result={'pass':c0_pass,","  rows=[] if budget.get('fixture') else (rows if monitor.exists() else [])\n  result={'pass':c0_pass,")
(R/'worker_t18.py').write_text(s)
print('worker written',len(s))
