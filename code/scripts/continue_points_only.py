"""Resume frozen C campaign after m02, reducing pressure in Colab without region uploads."""
import json,sys,time,datetime,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import orchestrate_new as old
R=old.R; S=old.S; RATE=old.RATE
M03_START=datetime.datetime.fromisoformat('2026-10-16T00:03:08.023410-04:00')
prior=[1.716930218936662,1.646024178230857]
# Conservative forward rate is based on observed computation plus existing upload overhead.
# Reference 2 CU and reserve 3 CU are explicitly retained from original controller.

def budget(k):
    uploaded_m01= (datetime.datetime.fromisoformat('2026-10-15T22:22:29.618744-04:00')-datetime.datetime.fromisoformat('2026-10-15T22:17:07.153780-04:00')).total_seconds()/3600
    no_upload=max(prior[0]-uploaded_m01, prior[1]-(3/60))
    estimate=max(1.4,no_upload,*(prior[2:] or [0]))
    projected=2+(sum(prior)+(11-k)*estimate)*RATE+3
    old.rec('POINTS_ONLY_CU_FORECAST',member=k,projected_cu=projected,actual_session_hours=prior,estimated_future_hours=estimate)
    if projected>100:raise RuntimeError(f'CU forecast {projected:.2f} >100; do not allocate member {k}')

def member(k):
    budget(k);old.remote_check()
    s=f'wx-cnew-m{k:02d}-1015';m=f'/content/ace_formal/members/m{k:02d}';base='/content/ace_formal'
    out=R/'results'/f'm{k:02d}'
    if k==3:
        assert out.is_dir() and not any(out.iterdir()),'unsafe m03 local result'
        start=M03_START
        old.watch(s,base+'/staging_2010.done',base+'/staging_2010.log',4)
        old.unwatch(s)
        x=old.query(s,f"import json;print('WXSTAGE '+json.dumps(json.load(open('{base}/staging_manifest_2010.json'))))\n")
        assert len(json.loads(x.split('WXSTAGE ',1)[1].splitlines()[0])['files'])==35
        old.rec('RESUME_STAGED_M03',session=s)
    else:
        if out.exists():raise RuntimeError('existing member result, refuse duplicate '+str(out))
        out.mkdir(parents=True,exist_ok=False)
        old.cli('new','-s',s,'--gpu','A100',timeout=300);old.rec('ALLOCATED',session=s)
        start=datetime.datetime.now().astimezone()
        old.cli('install','-s',s,'fme==2026.8.1','huggingface_hub','netcdf4',timeout=1200)
        old.cli('restart-kernel','-s',s,timeout=240)
        old.query(s,"from pathlib import Path;Path('/content/ace_formal').mkdir(parents=True,exist_ok=True);print('WXDIR_READY')\n")
        for name in ('stage_2010.py','launch_stage_2010.py','reduce_points.py','sites_frozen.json','launch_2010.py'):
            old.upload(s,(R/name if name=='sites_frozen.json' else S/name),base+'/'+name)
        old.upload(s,R/'threshold.json',base+'/threshold.json')
        old.query(s,f"exec(open('{base}/launch_stage_2010.py').read())\n")
        old.watcher(s,base+'/staging_2010.log',base+'/staging_2010.done')
        old.watch(s,base+'/staging_2010.done',base+'/staging_2010.log',4)
        old.unwatch(s)
        x=old.query(s,f"import json;print('WXSTAGE '+json.dumps(json.load(open('{base}/staging_manifest_2010.json'))))\n")
        assert len(json.loads(x.split('WXSTAGE ',1)[1].splitlines()[0])['files'])==35
    # The launcher hardcodes run_member_2010.py; install reduced implementation there.
    old.upload(s,S/'run_member_points_only.py',base+'/run_member_2010.py')
    x=old.cli('exec','-s',s,'--env',f'MONTH={k}','--timeout','70','-f',str(S/'launch_2010.py'),timeout=200)
    assert f'MEMBER_STARTED m{k:02d}' in x,x
    old.rec('MODEL_STARTED',session=s,member=k,mode='points_pressure_only')
    old.watcher(s,m+'/model.log',m+'/complete.done')
    old.watch(s,m+'/complete.done',m+'.launcher.log',7)
    x=old.query(s,f"import json;print('WXEXIT '+json.dumps(json.load(open('{m}/exit.json'))))\n")
    assert json.loads(x.split('WXEXIT ',1)[1].splitlines()[0])['returncode']==0,x
    for fn in ('summary.json','exit.json','pressure_minima.json','config.yaml'):
        old.download(s,m+'/'+fn,out/fn)
    p=json.loads((out/'pressure_minima.json').read_text());assert len(p['rows'])==30 and all(q['minimum_anomaly_pa']<0 for q in p['rows'])
    old.stop(s)
    hours=(datetime.datetime.now().astimezone()-start).total_seconds()/3600
    prior.append(hours)
    old.rec('MEMBER_COMPLETE',member=k,session=s,session_hours=hours,estimated_cu=hours*RATE,mode='points_pressure_only')

def main():
    assert not Path('/proc/2953162').exists(),'old orchestrator still running'
    manifest=json.loads((R/'results/m02/tacc_manifest.json').read_text())
    assert len(manifest['entries'])==32,'m02 region upload not preserved'
    old.rec('RESUME_AFTER_M02',reason='m02 finished; m03 staging allocated by former controller before pause; no model started')
    for k in range(3,11):member(k)
    old.rec('ALL_COMPLETE',member_count=10,estimated_cu=(2+sum(prior)*RATE+3))
if __name__=='__main__':
    try:main()
    except Exception as e:
        old.rec('HALTED_LEAVE_SESSION_RUNNING',error=repr(e));raise
