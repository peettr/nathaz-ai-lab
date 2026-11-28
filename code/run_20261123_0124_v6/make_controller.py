from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'controller_hardened.py').read_text()
s=s.replace('RATE=5.4; CAP=11.5','RATE=5.4; CAP=13.1')
s=s.replace("CASES=('t15_s1','t15_s2')","CASES=('K1a_s1','K1b_s1','K2_s1','K3a_s1','K3b_s1')")
s=s.replace('T17 big6v3 T15 #5cfca225','T18 C01 #9ab25d8a')
s=s.replace("if plan['two_case_upper_CU']>=CAP:","if plan['full_chain_upper_CU']>=CAP:")
s=s.replace("'two_case_upper_CU'","'full_chain_upper_CU'")
s=s.replace("plan['first_case_upper_CU']","plan['first_case_upper_CU']")
s=s.replace("2*plan['worst_case_solver_s']+plan['fixed_overhead_s']","plan['full_chain_upper_s']")
s=s.replace("'budget cannot fit two cases'","'full chain prelaunch budget cannot fit'")
s=s.replace("'steps_per_second':plan['steps_per_second']","'steps_per_second':plan['steps_per_second']")
s=s.replace("   if result=='session_absent':released=True","   if result=='session_absent':released=True")
old="""      if names!=list(CASES)[:len(names)] or acked!=names or any(x+'_case.json' not in verified or x+'_windows.json' not in verified for x in names):return 'failed'
      return 'budget_stop' if done.get('budget_stop') else 'done'"""
new="""      c0='C0_verdict.json'
      if c0 not in verified or 'C0_K3a_solver.log' not in verified:return 'failed'
      smoke=json.loads((e/c0).read_text())
      if smoke.get('fixture_only'):return 'failed'
      if smoke.get('pass') and 'C0_rho_monitor.csv' not in verified:return 'failed'
      expected=list(CASES if smoke.get('pass') else CASES[:3])
      if names!=expected[:len(names)] or acked!=names or any(x+'_case.json' not in verified or x+'_windows.json' not in verified for x in names):return 'failed'
      if not done.get('budget_stop') and names!=expected:return 'failed'
      return 'budget_stop' if done.get('budget_stop') else 'done'"""
assert old in s;s=s.replace(old,new)
s=s.replace("['B0','K1a','K1b','K2','K3a','K3b']","['B0','K1a','K1b','K2','K3a','K3b']")
# Even a short failed compile must pull logs before stop.
s=s.replace("   if 'run.failed' in verified:return 'failed'","   if 'run.failed' in verified:return 'failed'")
s=s.replace("   log('STOP_REASON',result)","   log('STOP_REASON',result)")
(R/'controller_t18.py').write_text(s)
print('controller generated',len(s))
