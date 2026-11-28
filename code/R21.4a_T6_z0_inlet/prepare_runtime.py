#!/usr/bin/env python3.10
"""Freeze a distinct T6 runner from verified T5 retry2 scripts (no GPU)."""
import pathlib,hashlib,json,tarfile,difflib
R=pathlib.Path(__file__).resolve().parent
P=R.parent/'R21.4a_T5_caseE_WM_retry2'
fit=json.loads((R/'fit.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'stage_t6.tar.gz')==fit['t6_archive_sha256']
with tarfile.open(R/'stage_t6.tar.gz') as t:
    setup=t.extractfile('stage/FluidX3D_on/src/setup.cpp').read().decode()
    assert setup.count(fit['actual_source_line'])==1
    m=json.load(t.extractfile('stage/manifest.json'))
    assert m['source']['on']['setup.cpp']==fit['t6_setup_sha256']
    assert all(m['cases'][f'E_s{s}_on']['config_sha256']==fit['t5_config_sha256'][str(s)] for s in (101,102))
for name in ('gpu_probe.py','abort_prelaunch.py'):
    p=R/name; data=(P/name).read_bytes()
    if p.exists():assert p.read_bytes()==data
    else:p.write_bytes(data)
changes={
 'worker.py':[
  ('"""Remote GPU worker: only E_s102_off; host SHA ACK required."""','"""T6 two enabled cases; host SHA ACK per case."""'),
  ("O=R/'t5_out'","O=R/'t6_out'"),
  ("CASES=['E_s102_off']","CASES=['E_s101_on','E_s102_on']"),
  ("R/'stage_t5.tar.gz'","R/'stage_t6.tar.gz'"),
  ("os.environ['T5_DEADLINE']","os.environ['T6_DEADLINE']"),
  ("for mode in ('off',):","for mode in ('on',):"),
  ("R/'t5_cases'","R/'t6_cases'"),
  ("(O/'run.done').write_text('E_s102_off complete\\n')","(O/'run.done').write_text('E_s101_on E_s102_on complete\\n')"),
  ("  cl=O/f'{label}_actual_opencl.cl';assert cl.is_file()","  cl=O/f'{label}_actual_opencl.cl';assert cl.is_file() and cl.read_text().count('9.04331419233e-05f')>=1, 'T6 z0 absent from executed OpenCL'"),
 ],
 'launch.py':[(".t5_launched",".t6_launched"),("/content/t5.log","/content/t6.log")],
 'probe.py':[("/content/t5_out","/content/t6_out"),("/content/t5.log","/content/t6.log")],
 'ack.py':[("/content/t5_out","/content/t6_out"),("T5_ACK_LABEL","T6_ACK_LABEL"),("T5_ACK_PAIR","T6_ACK_PAIR"),("assert label in ('E_s101_off','E_s101_on','E_s102_off','E_s102_on')","assert label in ('E_s101_on','E_s102_on')")],
 'controller.py':[
  ('"""Single-case T5 Colab controller, Linux scratch spool on ./ EIO."""','"""T6 two-case Colab controller, Linux scratch spool on ./ EIO."""'),
  ("'luw-t5-retry2-spool'","'luw-t6-z0-inlet-spool'"),
  ("NAME='luw-r214a-t5-casee-retry2-1117';LABEL='E_s102_off'","NAME='luw-r214a-t6-z0inlet-1117';LABELS=('E_s101_on','E_s102_on')"),
  ("'stage_t5.tar.gz'","'stage_t6.tar.gz'"),
  ("'R21.4a-T5 retry2 researchos-uwind-luw '","'R21.4a-T6 researchos-uwind-luw '"),
  ("for gpu in ('A100','G4'):","for gpu in ('G4','A100'):"),
  ("rate=5.4 if gpu=='A100' else 6.81;deadline=created+4.75/rate*3600","rate=5.4 if gpu=='A100' else 6.81;deadline=created+5.7/rate*3600"),
  ("cap_CU=5","cap_CU=6"),
  ("assert deadline-time.time()>1850","assert deadline-time.time()>2400"),
  ("'T5_DEADLINE'","'T6_DEADLINE'"),
  ("'/content/t5.log'","'/content/t6.log'"),
  ("/content/t5_out","/content/t6_out"),
  ("'--max-hours','2'","'--max-hours','2'"),
  ("'A100 and G4 allocation refused'","'G4 and A100 allocation refused'"),
  ("if verified:\n     stop('terminal_verified')","if len(verified)==len(LABELS):\n     stop('terminal_verified')"),
 ],
}
# Controller has a per-case verification loop and must not stop on the first ACK.
old=(P/'controller.py').read_text()
start=old.index('def verify(state):')
end=old.index('def stop(reason):')
verify='''def verify(state,label):
 pair=[]
 for ext in ('thin.npz','points80.json'):
  key=f'{label}_{ext}.sha256';info=state['ready'][key]
  p=pull('/content/t6_out/'+label+'_'+ext,label+'_'+ext)
  assert sha(p)==info['sha'] and p.stat().st_size==info['size']
  assert pull('/content/t6_out/'+key,key).read_text().strip()==info['sha']
  pair.append(info['sha'])
 d=json.loads((O/(label+'_points80.json')).read_text());assert d['label']==label and len(d['rows'])==80 and set(int(x['id']) for x in d['rows'])==set(range(1,81))
 for ext in ('solver.log','exit.json','actual_opencl.cl','ground_eligibility.csv','ground_excluded.csv','city_stability.csv','wall_tau_actual.csv'):
  pull('/content/t6_out/'+label+'_'+ext,label+'_'+ext,ext in ('solver.log','exit.json','actual_opencl.cl'))
 cl=O/(label+'_actual_opencl.cl');assert '9.04331419233e-05f' in cl.read_text()
 try:reply=execf(R/'ack.py',{'T6_ACK_LABEL':label,'T6_ACK_PAIR':' '.join(pair)})
 except (RuntimeError,subprocess.TimeoutExpired) as e:log('ack_uncertain',error=str(e)[-180:]);reply=''
 if 'ACK '+label not in reply:assert label+'.ack' in probe()['ack']
 verified.add(label);log('host_verified',label=label,thin_sha256=pair[0],points_sha256=pair[1],actual_opencl_sha256=sha(cl),spool=str(O))
'''
old=old[:start]+verify+old[end:]
old=old.replace('verified=False;launched=False','verified=set();launched=False')
old=old.replace("   keys=[LABEL+'_'+x+'.sha256' for x in ('thin.npz','points80.json')]\n   if all(k in state['ready'] for k in keys) and not verified:\n    try:verify(state)\n    except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError) as e:log('transfer_or_ack_error',error=str(e)[-250:])", "   for label in LABELS:\n    keys=[label+'_'+x+'.sha256' for x in ('thin.npz','points80.json')]\n    if all(k in state['ready'] for k in keys) and label not in verified:\n     try:verify(state,label)\n     except (subprocess.TimeoutExpired,RuntimeError,AssertionError,OSError,ValueError) as e:log('transfer_or_ack_error',label=label,error=str(e)[-250:])")
old=old.replace("stop_authorized',reason=reason,verified=verified)","stop_authorized',reason=reason,verified=sorted(verified))")
old=old.replace("if probe()['failed']:stop('terminal_verified')","if probe()['failed']:stop('terminal_verified')")
for name, edits in changes.items():
 text=old if name=='controller.py' else (P/name).read_text()
 for a,b in edits:
  if a==b:continue
  assert a in text,(name,a)
  text=text.replace(a,b)
 target=R/name
 if target.exists():assert target.read_text()==text,('existing script differs',name)
 else:target.write_text(text)
 if name=='controller.py':
  assert 'for label in LABELS:' in text and 'len(verified)==len(LABELS)' in text
  assert 'LABEL+' not in text and 't5_out' not in text
print('T6 scripts frozen:',[(n,sha(R/n)) for n in changes])
