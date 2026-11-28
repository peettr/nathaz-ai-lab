"""Bounded single-owner Colab group runner; each completed group immediately downloaded."""
import json,re,subprocess,time,datetime,pathlib,sys
D=pathlib.Path(__file__).parent;R=D.parent;CFG=D/'colab_state.json';S='ideas-convective-r2-v1seg2-1014'
START_BALANCE=1396.12
# Shared balance is a conservative upper bound on our own spending.
STOP_BALANCE=1378.12
N=1

def call(args,timeout=900,log=None):
    if log:
        with open(log,'x') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
        return r.returncode,log.read_text(errors='replace')[-3000:]
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    return r.returncode,r.stdout+r.stderr

def cli(*args):return ['colab','--auth','oauth2','--config',str(CFG),*args]
def audit(event,**kw):
    with (D/'runner_audit.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.datetime.now().astimezone().isoformat(),'event':event,**kw})+'\n')

try:
    while True:
        rc,u=call(['colab','--auth','oauth2','usage'],timeout=100)
        m=re.search(r'Current balance:\s*([\d.]+)',u)
        if rc or not m:raise RuntimeError('usage unavailable: '+u[-700:])
        balance=float(m.group(1));audit('usage',balance=balance,account_delta=round(START_BALANCE-balance,2),raw=u[-300:])
        if balance<=STOP_BALANCE:
            audit('budget_stop',balance=balance);break
        # One cell contains <=10 forecasts; check budget at this boundary.
        log=D/f'group_{N:03}.log'
        try:rc,excerpt=call(cli('exec','-s',S,'--timeout','1100','-f',str(R/'run_v1_segment2_group.py')),timeout=1200,log=log)
        except subprocess.TimeoutExpired as ex:
            audit('exec_timeout',group=N,error=str(ex));break
        audit('exec',group=N,exit=rc,excerpt=excerpt[-1000:])
        # Never overwrite a previously archived checkpoint.
        dest=D/f'checkpoint_group{N+1:03}.jsonl'
        drc,dout=call(cli('download','-s',S,'/content/r2_v1_main.jsonl',str(dest)),timeout=180)
        audit('pull',group=N,exit=drc,path=str(dest),message=dout[-500:])
        if drc or not dest.is_file():break
        records=[json.loads(x) for x in dest.read_text().splitlines()]
        counts={}
        for x in records:
            if x.get('status')=='ok':counts[(x['id'],x['lead_h'],x['source'])]=counts.get((x['id'],x['lead_h'],x['source']),0)+1
        complete=sum(v==10 for (eid,lead,src),v in counts.items() if src=='v1')
        audit('checkpoint',group=N,rows=len(records),complete_groups=complete)
        if 'SEGMENT_ALL_DONE' in excerpt or rc or 'GROUP_DONE' not in excerpt:break
        N+=1
except Exception as ex:
    audit('error',kind=type(ex).__name__,message=str(ex))
finally:
    # Only the session exclusively owned by this segment is stopped.
    rc,out=call(cli('stop','-s',S),timeout=150)
    audit('stop',exit=rc,message=out[-800:])
    rc,out=call(['colab','--auth','oauth2','sessions'],timeout=100)
    audit('sessions',exit=rc,own_present=S in out,raw=out[-1500:])
    rc,out=call(['colab','--auth','oauth2','usage'],timeout=100)
    audit('usage_after',exit=rc,raw=out[-500:])
