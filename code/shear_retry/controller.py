#!/usr/bin/env python3
"""Bounded A100/G4 allocation and isolated try13 shear fixture (Colab only)."""
import csv, hashlib, json, os, re, subprocess, sys, time, traceback
from pathlib import Path
R=Path(__file__).resolve().parent
SOURCE=R.parent/'shear_stage'
NAME='luw-t4-try13-shear-retry-1116'
CFG=R/'sessions.json'
BASE=['colab','--auth','oauth2','--config',str(CFG)]
GLOBAL=['colab','--auth','oauth2','sessions']
CTX=os.environ.get('RC_DELEGATE_CTX','')
created=False
created_at=None
gpu=None
allocated=False
log=R/'events.jsonl'
def record(event,**kw):
    row={'time':time.strftime('%m-%d %H:%M:%S %Z'),'event':event,**kw}
    with log.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row,ensure_ascii=False),flush=True)
def call(args,timeout=120,check=True):
    p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    text=p.stdout+'\n'+p.stderr
    text=re.sub(r'colab-runtime-proxy-token=[已隐去]','colab-runtime-proxy-token=[已隐去]',text)
    record('command',argv=args[:3]+args[3:],rc=p.returncode,output=text[-800:])
    if check and p.returncode:raise RuntimeError('command failure: '+text[-800:])
    return text
def cli(*args,timeout=120,check=True):return call(BASE+list(args),timeout,check)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def session_exists():return NAME in call(GLOBAL,timeout=60)
def precheck():
    manifest=json.loads((SOURCE/'shear_manifest.json').read_text())
    assert sha(SOURCE/'try13_shear.tar.gz')==manifest['archive_sha256']
    for name,digest in manifest['sources'].items():assert sha(SOURCE/'FluidX3D_gate0/src'/name)==digest,name
    assert not log.exists() and not (R/'.colab_owner').exists(),'retry root already used'
    assert not session_exists(),'session name occupied'
    with (R/'.colab_owner').open('x') as f:f.write('#c76a4d61 '+NAME+' '+time.strftime('%m-%d %H:%M %Z')+'\n')
    record('precheck_pass',archive_sha=manifest['archive_sha256'])
def allocate():
    global created,created_at,gpu,allocated
    start=time.monotonic();round_no=0
    while time.monotonic()-start<4*3600:
        round_no+=1
        for shape in ('A100','G4'):
            if time.monotonic()-start>=4*3600:break
            record('allocation_attempt',round=round_no,gpu=shape)
            try:
                cli('new','-s',NAME,'--gpu',shape,timeout=150)
                created=True;created_at=time.time();gpu=shape;allocated=True
                record('allocated',gpu=shape,created_at=created_at)
                return
            except Exception as exc:
                # An ambiguous allocation must never trigger a second new.
                if session_exists():
                    created=True;created_at=time.time();gpu=shape
                    record('ambiguous_allocation_live',gpu=shape,error=str(exc)[-500:])
                    raise
                if isinstance(exc,subprocess.TimeoutExpired):raise
                if not re.search(r'503|412|Service Unavailable|Allocation refused',str(exc),re.I):raise
                record('allocation_refused',round=round_no,gpu=shape,error=str(exc)[-500:])
        remaining=4*3600-(time.monotonic()-start)
        pause=min(max(0,start+round_no*1200-time.monotonic()),max(0,remaining))
        if pause:record('backoff_seconds',duration=round(pause));time.sleep(pause)
    raise RuntimeError('allocation_window_exhausted_4h')
def run_fixture():
    assert allocated
    # Conservative single-session cap: 3 hours on A100, 8 hours on G4,
    # with time for transfer/stop; earlier task CU remains unverified.
    limit=3*3600 if gpu=='A100' else 8*3600
    deadline=created_at+limit
    for local,remote in ((SOURCE/'try13_shear.tar.gz','/content/try13_shear.tar.gz'),(SOURCE/'shear_manifest.json','/content/shear_manifest.json'),(SOURCE/'run_shear.py','/content/run_shear.py')):
        cli('upload','-s',NAME,str(local),remote,timeout=180)
    try:
        response=cli('exec','-s',NAME,'-f',str(SOURCE/'launch_shear.py'),timeout=120)
    except (RuntimeError,subprocess.TimeoutExpired):
        # Do not launch again; read-only probe determines if launch occurred.
        response=cli('exec','-s',NAME,'-f',str(R/'probe.py'),timeout=90)
        if 'SHEAR_PROBE' not in response or 'lock True' not in response:raise RuntimeError('launch ambiguous; no relaunch')
    record('launcher_response',text=response[-500:])
    # Must use actual remote command-line fragment; worker launcher invokes this path.
    ka=[str(Path.home()/'bin/colab-keepalive'),'--config',str(CFG),'-s',NAME,'--log','/content/try13_shear_launcher.log','--proc','/content/run_shear.py','--stale-min','180','--until-marker','/content/try13_shear.done','--final-pull','/content/try13_shear_wall.csv:'+str(R/'final'),'--final-pull','/content/try13_shear_launcher.log:'+str(R/'final'),'--final-pull','/content/try13_shear_work/*.log:'+str(R/'final'),'--max-hours','8','--expect-hours','4','--detach']
    if CTX:ka+=['--ctx',CTX]
    call(ka,timeout=120)
    record('keepalive_started')
    while time.time()<deadline-600:
        time.sleep(45)
        p=R/'final/try13_shear_wall.csv'
        if p.exists() and p.stat().st_size>0:
            record('final_pull_seen',bytes=p.stat().st_size)
            break
        state=Path.home()/'platform/colab-keepalive'/f'{NAME}.json'
        if state.exists():
            st=json.loads(state.read_text())
            if st.get('state') not in (None,'running','done'):
                record('keepalive_terminal',state=st.get('state'),final_pulled=st.get('final_pulled'))
                raise RuntimeError('keepalive failed before completed evidence')
    else:raise RuntimeError('session_time_budget_exhausted')
    # Verify remote bytes before reporting the numerical gate.
    remote=cli('exec','-s',NAME,'-f',str(R/'probe.py'),timeout=90)
    found=re.search(r'SHEAR_SHA ([0-9a-f]{64})',remote)
    assert found and sha(R/'final/try13_shear_wall.csv')==found.group(1),'CSV remote hash mismatch'
    with (R/'final/try13_shear_wall.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==2001 and [int(x['step']) for x in rows]==list(range(2001))
    p0=float(rows[0]['px']); cumulative=0.0; worst=0.0;worst_step=0
    for r in rows[1:21]:
        cumulative+=float(r['wall_fx_sum'])
        residual=abs(float(r['px'])-p0-cumulative)
        if residual>worst:worst=residual;worst_step=int(r['step'])
    limit=abs(p0)*1e-4
    report={'rows':len(rows),'px0':p0,'max_residual_20':worst,'max_residual_step':worst_step,'limit':limit,'passed':worst<=limit,'csv_sha256':found.group(1),'session':NAME,'gpu':gpu,'created_at':created_at}
    (R/'gate.json').write_text(json.dumps(report,indent=2)+'\n')
    record('fixture_gate',**report)
    if not report['passed']:raise RuntimeError('fixture A scientific gate failed; no dependent stages')
    # No downstream job staged yet. Do not idle and lose evidence or bill CU.
def stop():
    if not created:return
    try:
        for remote,local in (('/content/try13_shear_launcher.log','launcher.log'),('/content/try13_shear.failed','failed.txt')):
            target=R/local
            if not target.exists():
                try:cli('download','-s',NAME,remote,str(target),timeout=120)
                except Exception as exc:record('optional_pull_error',file=remote,error=str(exc)[-180:])
        if not (R/'final/try13_shear_wall.csv').exists():
            try:cli('download','-s',NAME,'/content/try13_shear_wall.csv',str(R/'emergency_wall.csv'),timeout=120)
            except Exception as exc:record('emergency_pull_error',error=str(exc)[-180:])
        cli('stop','-s',NAME,timeout=120)
        record('stop_confirmed',absent=not session_exists(),estimated_session_hours=(time.time()-created_at)/3600)
    except Exception as exc:record('stop_error',error=str(exc)[-300:])
if __name__=='__main__':
    code=0
    try:precheck();allocate();run_fixture()
    except BaseException:record('controller_failed',trace=traceback.format_exc()[-2500:]);code=2
    finally:stop()
    sys.exit(code)
