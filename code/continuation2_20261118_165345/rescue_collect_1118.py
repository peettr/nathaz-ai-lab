#!/usr/bin/env python3
"""Collect/ACK existing T15 VM only; never allocate or launch solver."""
import csv, hashlib, json, os, pathlib, re, subprocess, time, traceback
R=pathlib.Path(__file__).resolve().parent
D=R/'session_luw-t15-a100-adacd84b'; O=D/'evidence'; CFG=D/'sessions.json'; NAME='luw-t15-a100-adacd84b'; EP='gpu-a100-s-ass1b0-ignfsduhw5sq'
BASE=['colab','--auth','oauth2']; CASES=('E3_native','WM_s107','WM_s108','WM_s109','K3_s107')
CUT=json.loads((D/'t15_budget.json').read_text())['work_deadline']; HARD=CUT+180
LOG=R/'rescue_events_1118.log'
def log(*v):
 s=time.strftime('%Y-%m-%d %H:%M:%S %Z')+' '+' '.join(map(str,v));print(s,flush=True)
 try:
  with LOG.open('a') as f:f.write(s+'\n')
 except OSError:pass
def cli(parts,t=45):
 try:
  p=subprocess.run(BASE+['--config',str(CFG),parts[0],'-s',NAME]+parts[1:],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=min(t,max(1,CUT-time.time())),stdin=subprocess.DEVNULL)
  if p.returncode:raise OSError(p.stdout[-1000:])
  return p.stdout
 except subprocess.TimeoutExpired as e:raise OSError('CLI_TIMEOUT ambiguous '+str(e))
def remote(code):
 f=D/'rescue_probe_readonly.py';f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_io_full as io\n"+code+'\n')
 return cli(['exec','-f',str(f)])
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def retry(fn,label):
 for i in range(5):
  if time.time()>=CUT:raise TimeoutError('cutoff')
  try:return fn()
  except (OSError,TimeoutError) as e:
   log('RETRY',label,i+1,repr(e))
   if i==4:raise
   time.sleep(min(30*2**i,max(0,CUT-time.time())))
def probe():
 s=retry(lambda:remote("print('T15_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)"),'probe');rows=[x[len('T15_PROBE '):] for x in s.splitlines() if x.startswith('T15_PROBE ')]
 if len(rows)!=1:raise OSError('missing probe tag')
 return json.loads(rows[0])
def download(n):
 target=O/(n+'.rescue.partial');retry(lambda:cli(['download','/content/t15/out/'+n,str(target)],60),'download '+n)
 return target
def ack(label,hashes):
 pending=D/(label+'.rescue.ack.pending');pending.write_text(json.dumps(hashes));retry(lambda:cli(['upload',str(pending),'/content/'+label+'.ack.pending'],55),'upload ACK '+label)
 # Remote ack is idempotent only after checking existing ACK.
 for i in range(5):
  s=remote("import pathlib; p=io.C/'t15/out/"+label+".ack.json'; print('ACK_EXISTS',p.is_file(),p.read_text() if p.is_file() else '',flush=True)")
  row=next((x for x in s.splitlines() if x.startswith('ACK_EXISTS ')),None)
  if row and row.startswith('ACK_EXISTS True '):
   if json.loads(row[len('ACK_EXISTS True '):])!=hashes:raise ValueError('remote ACK mismatch '+label)
   return
  try:retry(lambda:remote('io.ack(io.C,'+repr(label)+')'),'exec ACK '+label);return
  except (OSError,TimeoutError) as e:log('ACK_RECHECK',label,repr(e))
 raise OSError('ACK not confirmed '+label)
def main():
 log('RESUME_EXISTING_ONLY',EP,'cut',CUT,'hard',HARD)
 name_map=json.loads(CFG.read_text());assert name_map[NAME]['endpoint']==EP
 global_list=subprocess.run(BASE+['sessions'],capture_output=True,text=True,timeout=25).stdout
 assert EP in global_list
 verified={};acks=[]
 for n in O.iterdir():
  if n.name.endswith('.sha256'):continue
  side=O/(n.name+'.sha256')
  if side.is_file() and sha(n)==side.read_text().strip():verified[n.name]=sha(n)
 for label in CASES:
  if (O/(label+'_handoff.json')).exists() and (O/(label+'_exit.json')).exists():
   try:
    hashes=json.loads((O/(label+'_handoff.json')).read_text())['sha256']
    if all(verified.get(k)==v for k,v in hashes.items()):
     s=remote("import pathlib; print('ACK_EXISTS', (io.C/'t15/out/"+label+".ack.json').exists())")
     if 'ACK_EXISTS True' in s:acks.append(label)
   except (OSError,KeyError,ValueError):pass
 log('RECOVERED',len(verified),acks)
 result='deadline'
 while time.time()<CUT:
  try:
   listing=probe()
   for n,info in listing.items():
    if n in verified:continue
    if not re.fullmatch(r'[\w.-]+',n) or n.endswith('.vtk'):raise ValueError('unsafe output '+n)
    p=download(n);s=download(n+'.sha256')
    h=sha(p)
    if not(h==info['sha']==s.read_text().strip() and p.stat().st_size==info['size']>0):raise OSError('transfer inconsistent '+n)
    p.replace(O/n);s.replace(O/(n+'.sha256'));verified[n]=h;log('VERIFIED',n,h)
   if len(acks)<len(CASES):
    label=CASES[len(acks)];hand=label+'_handoff.json'
    if hand in verified:
     hashes=json.loads((O/hand).read_text())['sha256']
     if set(hashes)<=set(verified) and all(verified[k]==v for k,v in hashes.items()):
      if json.loads((O/(label+'_exit.json')).read_text())['solver_exit']!=0:raise ValueError('solver exit '+label)
      if label=='E3_native':
       with (O/(label+'_native_e3.csv')).open() as f:rows=list(csv.DictReader(f))
       if not rows or max(float(x['relative_error']) for x in rows)>1e-6:raise ValueError('E3 failed')
      elif 'A100' not in (O/(label+'_solver.log')).read_text(errors='replace'):raise ValueError('device not A100')
      ack(label,hashes);acks.append(label);log('ACK',label)
   if 'run.failed' in verified:result='failed';break
   if 'run.done' in verified:
    done=json.loads((O/'run.done').read_text());result='done' if done=={'verified_cases':list(CASES),'mode':'production'} and acks==list(CASES) else 'failed';break
  except (OSError,TimeoutError) as e:log('RETRY_NO_STOP',repr(e))
  except Exception as e:log('GATE_ERROR',repr(e));result='gate_failure';break
  time.sleep(min(10,max(0,CUT-time.time())))
 log('STOP_REASON',result)
 # Stop only after verified terminal marker or deadline; a failed scientific gate is not a stop reason.
 if result not in ('done','failed','deadline') and time.time()<CUT:
  log('NO_STOP_CONDITION');return 3
 released=False
 for _ in range(3):
  try:log('STOP',cli(['stop'],35))
  except Exception as e:log('STOP_ERROR',repr(e))
  try:
   s=subprocess.run(BASE+['sessions'],capture_output=True,text=True,timeout=25)
   released=s.returncode==0 and EP not in s.stdout
   log('ENDPOINT_CHECK',released)
   if released:break
  except Exception as e:log('SESSION_CHECK_ERROR',repr(e))
 log('ENDPOINT',EP,'released',released,'CU_ESTIMATE',((time.time()-1795041046)*5.4/3600 if released else None))
 if released:
  subprocess.run(['systemctl','--user','stop','colab-keepalive-'+NAME],capture_output=True,text=True,timeout=25)
  s=subprocess.run([str(pathlib.Path.home()/'bin/colab-orphans')],capture_output=True,text=True,timeout=35);log('ORPHANS',s.stdout,s.stderr)
 return 0 if result=='done' and released else 2
if __name__=='__main__':raise SystemExit(main())
