#!/usr/bin/env python3
"""T15 same-endpoint recovery ONLY: read/ACK/stop, never allocate or launch."""
import csv,hashlib,json,pathlib,re,subprocess,time,uuid,sys
from controller_full import raw,checked,sha,retry,BASE,CASES,R,RATE
NAME='luw-t15-a100-4bb145f8';ENDPOINT='gpu-a100-s-usc1f0-1tb2l07d9z0r0'
D=R/('session_'+NAME);CFG=D/'sessions.json';OUT=D/'evidence';OUT.mkdir(exist_ok=True)
CUT=json.loads((D/'t15_budget.json').read_text())['work_deadline'];CREATED=CUT+180-15*3600/RATE
RECEIPT=json.loads((D/'t15_upload.json').read_text());VERIFIED={}
def cli(args,t=40):return raw(BASE+['--config',str(CFG),args[0],'-s',NAME]+args[1:],max(.1,min(t,CUT-time.time())))
def remote(code):
 f=D/('salvage_exec_'+uuid.uuid4().hex+'.py');f.write_text("import sys;sys.path.insert(0,'/content')\nimport remote_io_full as io\n"+code+'\n')
 return retry('salvage_exec',lambda:checked(cli(['exec','-f',str(f)],40)),CUT)
def probe():
 out=remote("print('T15_PROBE '+io.json.dumps(io.probe(io.C)),flush=True)")
 lines=[s[len('T15_PROBE '):] for s in out.splitlines() if s.startswith('T15_PROBE ')]
 if len(lines)!=1:raise OSError('probe missing')
 return json.loads(lines[0])
def pull(n):
 p=OUT/(n+'.partial');retry('pull '+n,lambda:checked(cli(['download','/content/t15/out/'+n,str(p)],75)),CUT)
 return p
def ack(label,data):
 p=D/(label+'.ack.recovery.pending');p.write_text(json.dumps(data))
 retry('ACK upload',lambda:checked(cli(['upload',str(p),'/content/'+label+'.ack.pending'],40)),CUT)
 remote("io.ack(io.C,"+repr(label)+")")
def main():
 if not (R/'.colab_owner').is_file():raise RuntimeError('not owned')
 s=checked(raw(BASE+['sessions']))
 if ENDPOINT not in s:raise RuntimeError('owned endpoint absent, reconcile; do not stop other sessions')
 state=checked(raw(BASE+['--config',str(CFG),'sessions']))
 if NAME not in state or ENDPOINT not in state:raise RuntimeError('named endpoint not proven')
 print('RESUME_SAME_ENDPOINT',NAME,ENDPOINT,'deadline',CUT,flush=True)
 acks=[];result='unconfirmed'
 try:
  while time.time()<CUT:
   try:
    listing=probe()
    for n,info in listing.items():
     if n in VERIFIED:continue
     if not re.fullmatch(r'[\w.-]+',n) or n in ('.','..') or n.endswith('.vtk'):raise ValueError('unsafe '+n)
     p=pull(n);hfile=pull(n+'.sha256');h=sha(p)
     if h!=hfile.read_text().strip() or h!=info['sha'] or p.stat().st_size!=info['size']:raise OSError('transfer hash mismatch '+n)
     p.replace(OUT/n);hfile.replace(OUT/(n+'.sha256'));VERIFIED[n]=h;print('VERIFIED',n,h,flush=True)
    if len(acks)<len(CASES):
     label=CASES[len(acks)];hand=label+'_handoff.json'
     if hand in VERIFIED:
      data=json.loads((OUT/hand).read_text())['sha256']
      if set(data)<=set(VERIFIED):
       if any(VERIFIED[k]!=v for k,v in data.items()):raise ValueError('handoff SHA '+label)
       if json.loads((OUT/(label+'_exit.json')).read_text())['solver_exit']!=0:raise ValueError('solver exit '+label)
       if label=='E2_off_s107' and json.loads((OUT/(label+'_bitwise.json')).read_text())['status']!='PASS':raise ValueError('E2 fail')
       if label=='E3_native':
        with (OUT/(label+'_native_e3.csv')).open() as f:rows=list(csv.DictReader(f))
        if not rows or any(float(x['relative_error'])>1e-6 for x in rows):raise ValueError('E3 fail')
       log=(OUT/(label+'_solver.log')).read_text(errors='replace')
       if 'NVIDIA A100-SXM4-40GB' not in log:raise ValueError('GPU solver device mismatch')
       ack(label,data);acks.append(label);print('ACK_SHA',label,len(data),flush=True)
    if 'run.failed' in VERIFIED:result='failed';break
    if 'run.done' in VERIFIED:
     end=json.loads((OUT/'run.done').read_text());result='done' if end=={'mode':'production','verified_cases':list(CASES)} and acks==list(CASES) else 'failed';break
   except (OSError,TimeoutError) as e:print('TRANSIENT_NO_STOP',repr(e),flush=True)
   time.sleep(min(8,max(0,CUT-time.time())))
  if time.time()>=CUT and result=='unconfirmed':result='deadline'
 finally:
  if result not in ('done','failed','deadline'):raise RuntimeError('no permitted stop gate')
  print('STOP_REASON',result,flush=True)
  released=False
  for _ in range(3):
   print('STOP',cli(['stop'],35),flush=True)
   rc,s=raw(BASE+['sessions'],20);released=rc==0 and ENDPOINT not in s
   if released:break
  print('ENDPOINT',ENDPOINT,'released',released,'CU_ESTIMATE',((time.time()-CREATED)*RATE/3600 if released else None),flush=True)
  print('KEEPALIVE_STOP',raw(['systemctl','--user','stop','colab-keepalive-'+NAME],20),flush=True)
  print('ORPHANS',raw([str(pathlib.Path.home()/'bin/colab-orphans')],35),flush=True)
 return 0 if result=='done' and released else 2
if __name__=='__main__':sys.exit(main())
