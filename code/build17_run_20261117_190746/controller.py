#!/usr/bin/env python3
"""Prepared A100-only transport; inert unless explicitly invoked for a future run."""
import argparse,hashlib,json,math,pathlib,re,subprocess,sys,time,uuid

R=pathlib.Path(__file__).resolve().parent
PAYLOAD=('t9b_v12_source.tar.gz','t9b_v12_manifest.json','v12_off_t5_environment.cl','stage_t5.tar.gz','archive.json','B2u_reference_points.json','remote_worker_run2.py','t5_sampling.py','worker_gate.py','remote_io.py','t9b17_budget.json')
CASES=('E_s101_off','E_s101_on','E_s102_on')
PRODUCTS=('solver.log','actual_opencl.cl','points80.json','fluid_mask.json','exit.json')
OFF_SHA='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
RATE=5.4
BASE=['colab','--auth','oauth2']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def talk(*v):print(*v,flush=True)
def clock(created):return dict(mode='production',created=created,rate=RATE,work_deadline=created+13*3600/RATE-150,stop_target=created+13*3600/RATE,hard_deadline=created+14*3600/RATE)

def files_for(label):
    names={f'{label}_{s}' for s in PRODUCTS}
    if label==CASES[0]:names|={'gate1.json','build_off.log'}
    if label==CASES[1]:names|={'gate3.json','points80_difference.json','build_on.log'}
    return names

def verify_schema(o,label,mode):
    p=json.loads((o/f'{label}_points80.json').read_text());rows=p['rows']
    if p['label']!=label or p['uref']!=3.9286416 or p['sample_height_above_wall_m']!=2.0 or p['vtk_label_z_m']!=2.5 or len(rows)!=80 or {x['id'] for x in rows}!=set(range(1,81)) or any(not math.isfinite(x['Su']) or not math.isfinite(x['Su_ratio']) or x['xyz_m'][2]!=2.5 for x in rows):raise ValueError('points schema '+label)
    mask=json.loads((o/f'{label}_fluid_mask.json').read_text()); dims=[500,500,270] if mode=='production' else [500,500,4]
    if mask['dims']!=dims or not 0<=mask['solid_cells']<=mask['total_cells']==math.prod(dims) or not re.fullmatch('[0-9a-f]{64}',mask['mask_sha256']):raise ValueError('mask schema '+label)
    if json.loads((o/f'{label}_exit.json').read_text())['solver_exit']!=0:raise ValueError('nonzero solver '+label)
    if label==CASES[0]:
        g=json.loads((o/'gate1.json').read_text());h=sha(o/f'{label}_points80.json')
        if h!=g['actual'] or (mode=='production' and g['target']!=OFF_SHA) or g['passed']!=(h==g['target']):raise ValueError('gate1 receipt')
    if mode=='production' and 'A100' not in (o/f'{label}_solver.log').read_text(errors='replace'):raise ValueError('missing A100 evidence '+label)
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
                    if mode=='production' and dev and 'A100' not in dev[-1]:raise RuntimeError('solver evidence did not confirm A100')
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
    frozen=json.loads((R/'PREFLIGHT.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py'})<=frozen.keys()
    if any(sha(R/n)!=h for n,h in frozen.items()):raise SystemExit('source seal mismatch')
    with (R/'.build17_run_claim').open('x') as mark:mark.write(str(time.time()))
    campaign=time.time()
    started=False
    for i in range(13):
        planned=campaign+1200*i
        if i and planned>campaign+14400:break
        time.sleep(max(0,planned-time.time()))
        name='luw-t9b17-a100-'+uuid.uuid4().hex[:8];d=R/('run_'+name);d.mkdir();cfg=d/'sessions.json';o=d/'evidence';o.mkdir()
        def cli(cmd,t=25):return raw(BASE+['--config',str(cfg),cmd[0],'-s',name]+cmd[1:],t)
        before=checked(raw(BASE+['sessions']));assert name not in before
        (d/'.owner').write_text(name+' '+str(time.time())+'\n')
        created=time.time();b=clock(created);rc,msg=cli(['new','--gpu','A100'],100);talk('ALLOCATION',name,rc,msg)
        sr,global_=raw(BASE+['sessions']);lr,local=raw(BASE+['--config',str(cfg),'sessions'])
        (d/'allocation.json').write_text(json.dumps(dict(attempt=i+1,name=name,request_at=created,rc=rc,response=msg,local=local,global_sessions=global_)))
        candidates=set(re.findall(r'gpu-a100-[a-z0-9-]+','\n'.join(x for x in local.splitlines() if name in x)+'\n'+msg))
        owned={x for x in candidates if x in global_ and x not in before}
        if len(owned)==1 and sr==0 and lr==0:
            started=True;break
        if sr==lr==0 and not owned and name not in local and name not in global_ and rc and re.search(r'503|Service Unavailable',msg,re.I):
            talk('CAPACITY_REFUSED_NO_SESSION',i+1);continue
        raise SystemExit('allocation ambiguous: no automatic retry, reconcile ownership')
    if not started:return 2
    ep=owned.pop();talk('OWNED_ENDPOINT',ep,b);cut=b['work_deadline'];deadline=b['hard_deadline'];ka=False;result='failed';may_live=False
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
    def download(n,tmp):checked(bounded(['download','/content/t9b17/out/'+n,str(tmp)]))
    def publish(label,data):
        p=d/(label+'.ack.json');p.write_text(json.dumps(data));upload(p,label+'.ack.pending');rc,out=exec_text(f'io.ack(io.C,{label!r})')
        if rc:
            rc,out=exec_text(f"print('ACK_OK', (io.C/'t9b17/out/{label}.ack.json').is_file(), flush=True)")
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
        receipt=d/'t9b17_upload.json';receipt.write_text(json.dumps(hashes));upload(receipt,receipt.name)
        if cut-time.time()<2*2520+2420:raise TimeoutError('remaining CU cannot cover three cases')
        may_live=True;talk('LAUNCH_REPLY',exec_text('io.launch(io.C)'))
        rc,out=raw([str(pathlib.Path.home()/'bin/colab-keepalive'),'--config',str(cfg),'-s',name,'--log','/content/t9b17.log','--until-marker','/content/t9b17/out/run.done','--max-hours','3','--expect-hours','2.4','--no-remind','--pull','/content/t9b17.log:'+str(d/'worker_progress.log'),'--detach'],45);ka=rc==0;talk('KEEPALIVE',rc,out)
        result=collect(o,probe,download,publish,cut,'production')
    except Exception as e:
        talk('ERROR',repr(e))
        # An ambiguous launched worker is not stopped just because an exec/probe failed.
        if may_live and time.time()<cut and isinstance(e,(TimeoutError,OSError)):
            result=collect(o,probe,download,publish,cut,'production')
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
