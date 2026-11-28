#!/usr/bin/env python3
"""Prepared A100-only transport; inert unless explicitly invoked for a future run."""
import argparse,hashlib,json,math,pathlib,re,subprocess,sys,time,uuid

R=pathlib.Path(__file__).resolve().parent
PAYLOAD=('stage_t5.tar.gz','archive.json','B2u_reference_points.json','comparison.json','setup_t11.cpp','setup_manifest.json','remote_worker_run2.py','t5_sampling.py','worker.py','remote_io.py','t11_budget.json')
CASES=('E_s101_off','E_s102_off')
PRODUCTS=('solver.log','actual_opencl.cl','points80.json','upstream_slice.npz','profile.json','exit.json')
OFF_SHA='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
RATE=5.4
BASE=['colab','--auth','oauth2']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def talk(*v):print(*v,flush=True)
def clock(created):return dict(mode='production',created=created,rate=RATE,work_deadline=created+10*3600/RATE-180,stop_target=created+10*3600/RATE,hard_deadline=created+11*3600/RATE)

def files_for(label):
    names={f'{label}_{x}' for x in PRODUCTS}
    if label==CASES[0]:names.add('build.log')
    return names

def verify_schema(o,label,mode):
    import numpy as np
    p=json.loads((o/f'{label}_points80.json').read_text());rows=p['rows']
    if p['label']!=label or p['uref']!=3.9286416 or p['sample_height_above_wall_m']!=2.0 or len(rows)!=80 or {x['id'] for x in rows}!=set(range(1,81)) or any(not math.isfinite(x['Su']) or x['xyz_m'][2]!=2.5 for x in rows):raise ValueError('points schema '+label)
    if json.loads((o/f'{label}_exit.json').read_text())['solver_exit']!=0:raise ValueError('solver exit '+label)
    with np.load(o/f'{label}_upstream_slice.npz') as n:
        if n['tke'].shape!=(62,201,61) or n['fluid'].shape!=(62,201,61) or not np.isfinite(n['tke']).all():raise ValueError('slice schema')
    q=json.loads((o/f'{label}_profile.json').read_text());profile=q['profile']
    if len(profile)!=18 or {(x['x_m'],x['height_agl_m']) for x in profile}!={(a,b) for a in (5,30,45) for b in (2.,5.,10.,15.9,25.,50.)}:raise ValueError('profile schema')
    text=(o/f'{label}_solver.log').read_text(errors='replace')
    if mode=='production' and ('NVIDIA A100-SXM4-40GB' not in text or '31000' not in text):raise ValueError('solver device/steps')
    print('SCHEMA_OK',label,flush=True)

def collect(o,probe,download,publish,deadline,mode):
    verified={};acks=[];miss=0;started=time.time()
    while time.time()<deadline:
        try:
            listed=probe();miss=0
            for n,info in listed.items():
                if n in verified:continue
                if not re.fullmatch(r'[\w.-]+',n) or n in ('.','..') or n.endswith('.vtk'):raise ValueError(n)
                for name in (n,n+'.sha256'):
                    tmp=o/(name+'.partial');download(name,tmp);tmp.replace(o/name)
                h=sha(o/n)
                if not ((o/n).stat().st_size==info['size']>0 and h==info['sha']==(o/(n+'.sha256')).read_text().strip()):raise ValueError('bad transfer '+n)
                verified[n]=h;talk('VERIFIED',n,h)
                if n.endswith('_solver.log'):
                    text=(o/n).read_text(errors='replace');dev=re.findall(r'(?m)^\| Device Name\s*\|\s*([^|\r\n]+)\|',text)
                    ml=re.findall(r'([0-9.]+)\s+MLUPs',text)
                    talk('SOLVER_DEVICE',n,dev[-1] if dev else None,'LAST_MLUPS',ml[-1] if ml else None)
                    if mode=='production' and (not dev or 'A100' not in dev[-1]):raise RuntimeError('solver evidence did not confirm A100')
            if len(acks)<len(CASES):
                label=CASES[len(acks)]; n=f'{label}_handoff.json'
                if n in verified:
                    handoff=json.loads((o/n).read_text());expected=files_for(label)
                    if expected!=handoff['sha256'].keys():raise ValueError('handoff file set')
                    if expected<=verified.keys():
                        values={k:verified[k] for k in expected}
                        if handoff['sha256']!=values:raise ValueError('handoff hash map')
                        verify_schema(o,label,mode);publish(label,values);acks.append(label);talk('ACK',label,'elapsed_s',round(time.time()-started))
            if 'run.failed' in verified:return 'failed'
            if 'run.done' in verified:
                done=json.loads((o/'run.done').read_text());return 'done' if done==dict(mode=mode,verified_cases=list(CASES)) and acks==list(CASES) else 'failed'
        except (OSError,TimeoutError) as e:
            miss+=1;talk('TRANSIENT_NO_STOP',repr(e),miss)
        time.sleep(.2 if mode!='production' else min(8,max(0,deadline-time.time())))
    return 'deadline'

def raw(args,limit=25):
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,stdin=subprocess.DEVNULL,timeout=limit);return p.returncode,p.stdout
    except subprocess.TimeoutExpired:return 124,'timeout'
def checked(pair):
    rc,out=pair
    if rc:raise OSError(out[-1200:])
    return out

def production(approved):
    if not approved:raise SystemExit('prep only; future explicit --authorized-run required')
    frozen=json.loads((R/'PREFLIGHT_v2.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py'})<=frozen.keys()
    if any(sha(R/n)!=h for n,h in frozen.items()):raise SystemExit('source seal mismatch')
    with (R/'.t11_run_claim').open('x') as mark:mark.write(str(time.time()))
    window=time.time();name=None;d=None;cfg=None;o=None;created=None;ep=None
    events=(R/'allocation_events.log').open('x',buffering=1);sys.stdout=events
    while time.time()-window<4*3600:
        name='luw-t11-a100-'+uuid.uuid4().hex[:8];d=R/('run_'+name);d.mkdir();cfg=d/'sessions.json';o=d/'evidence';o.mkdir()
        def cli(cmd,t=25):return raw(BASE+['--config',str(cfg),cmd[0],'-s',name]+cmd[1:],t)
        before=checked(raw(BASE+['sessions']));assert name not in before
        attempted=time.time();rc,msg=cli(['new','--gpu','A100'],100);talk('ALLOCATION',name,rc,msg)
        local=checked(raw(BASE+['--config',str(cfg),'sessions']));global_=checked(raw(BASE+['sessions']))
        candidates=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(x for x in local.splitlines() if name in x)+'\n'+msg))
        owned={x for x in candidates if x in global_ and x not in before}
        if len(owned)==1:
            ep=owned.pop();created=attempted;break
        if rc==0 or not re.search(r'503|412|Service Unavailable|Allocation refused|precondition failed',msg,re.I) or name in global_ or candidates:
            raise SystemExit('allocation ambiguous: reconcile global list; no duplicate allocation')
        talk('DEFINITE_CAPACITY_REFUSAL',name,'next attempt in 20 min with fresh name')
        left=window+4*3600-time.time()
        if left<=1200:break
        time.sleep(min(1200,max(0,attempted+1200-time.time())))
    if ep is None:talk('ALLOCATION_WINDOW_EXHAUSTED');return 2
    (d/'events.log').write_text('see ../allocation_events.log\n')
    b=clock(created);talk('OWNED_ENDPOINT',ep,b);cut=b['work_deadline'];deadline=b['hard_deadline'];ka=False;result='failed';may_live=False
    def bounded(cmd,t=25):
        left=cut-time.time()
        if left<=0:raise TimeoutError('work deadline')
        return cli(cmd,max(.1,min(t,left)))
    def upload(path,n):checked(bounded(['upload',str(path),'/content/'+n]))
    def exec_text(code):
        f=d/'remote_exec.py';f.write_text("import sys; sys.path.insert(0,'/content')\nimport remote_io as io\n"+code+'\n');return bounded(['exec','-f',str(f)],35)
    def probe():
        out=checked(exec_text("print('PROBE '+io.json.dumps(io.probe(io.C)),flush=True)"));rows=[x[6:] for x in out.splitlines() if x.startswith('PROBE ')]
        if len(rows)!=1:raise OSError('no probe record')
        return json.loads(rows[0])
    def download(n,tmp):checked(bounded(['download','/content/t11/out/'+n,str(tmp)]))
    def publish(label,data):
        p=d/(label+'.ack.json');p.write_text(json.dumps(data));upload(p,label+'.ack.pending');rc,out=exec_text(f'io.ack(io.C,{label!r})')
        if rc:
            rc,out=exec_text(f"print('ACK_OK', (io.C/'t11/out/{label}.ack.json').is_file(), flush=True)")
            if rc or 'ACK_OK True' not in out:raise OSError('unconfirmed ACK '+label)
    try:
        for _ in range(3):
            rc,msg=bounded(['exec','-f',str(R/'machine.py')],20);talk('MACHINE',rc,msg)
            rows=[x[12:] for x in msg.splitlines() if x.startswith('GPU_MACHINE ')]
            if rc==0 and rows:
                x=json.loads(rows[0]);m=re.fullmatch(r'([^,]+),\s*(\d+),\s*(\d+)',x['stdout'].strip()) if x['rc']==0 else None
                if m:
                    if 'A100' not in m[1] or int(m[3])<16000:raise ValueError('measured hardware mismatch')
                    break
        bp=d/PAYLOAD[-1];bp.write_text(json.dumps(b));hashes={}
        for n in PAYLOAD:
            f=bp if n==bp.name else R/n;upload(f,n);hashes[n]=sha(f)
        receipt=d/'t11_upload.json';receipt.write_text(json.dumps(hashes));upload(receipt,receipt.name)
        if cut-time.time()<2*2520:raise TimeoutError('remaining CU cannot cover two cases')
        may_live=True;talk('LAUNCH_REPLY',exec_text('io.launch(io.C)'))
        rc,out=raw([str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t11.log','--until-marker','/content/t11/out/run.done','--max-hours','3','--expect-hours','2.1','--no-remind','--pull','/content/t11.log:'+str(d/'worker_progress.log'),'--detach'],45);ka=rc==0;talk('KEEPALIVE',rc,out)
        result=collect(o,probe,download,publish,cut,'production')
    except Exception as e:
        talk('ERROR',repr(e))
        # An ambiguous launched worker is not stopped just because an exec/probe failed.
        if may_live and time.time()<cut:result=collect(o,probe,download,publish,cut,'production')
    finally:
        released=False
        for _ in range(3):
            talk('STOP',cli(['stop'],max(.1,min(32,deadline-time.time()))))
            sr,v=raw(BASE+['sessions'],max(.1,min(20,deadline-time.time())));released=sr==0 and ep not in v
            if released:break
        talk('ENDPOINT',ep,'released',released,'result',result,'CU estimate',((time.time()-created)*RATE/3600 if released else None))
        if ka:talk('KEEPALIVE_STOP',raw(['systemctl','--user','stop','colab-keepalive-'+name]))
        talk('ORPHANS',raw([str(pathlib.Path.home()/'bin/colab-orphans')],35))
    return 0 if result=='done' and released else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorized-run',action='store_true');sys.exit(production(p.parse_args().authorized_run))
