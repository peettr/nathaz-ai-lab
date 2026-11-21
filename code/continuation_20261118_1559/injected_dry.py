#!/usr/bin/env python3
"""E4 transport and real-worker exercise; no solver execution and no Colab."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tarfile,time
R=pathlib.Path(__file__).resolve().parent
BASE=R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/stage'
# The stage is sourced only from archived T4 physical configs and T15 private source.
import importlib.util
spec=importlib.util.spec_from_file_location('t13_controller',R.parents[1]/'R21.4a_T13_smag_cs010/T13b_20261118_104520/controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
real_sleep=c.time.sleep;c.time.sleep=lambda s:real_sleep(min(s,.01))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def retry(name,fn):return c.retry_step(name,fn,time.time()+1800)
def inject(name,fn):
    fired=[False]
    def wrapped(*args,**kwargs):
        if not fired[0]:
            fired[0]=True;print('INJECT_TIMEOUT',name,flush=True);raise OSError('timeout')
        return fn(*args,**kwargs)
    return wrapped,fired

def main():
    stage=R/'e4_stage_fixture';stage.mkdir(exist_ok=False)
    shutil.copytree(R/'FluidX3D_on',stage/'FluidX3D_on')
    original=json.loads((BASE/'phase_manifest.json').read_text())
    manifest={'source_on':{},'cases':{}}
    for name in original['source_on']:
        manifest['source_on'][name]=sha(stage/'FluidX3D_on/src'/name)
    for case in ('dx1p0_s107','dx1p0_s108','dx1p0_s109'):
        shutil.copytree(BASE/case,stage/case)
        manifest['cases'][case]={'conf_sha256':sha(stage/case/'conf.luwpf')}
    archive=R/'e4_stage_fixture.tar.gz'
    with tarfile.open(archive,'x:gz') as tf:tf.add(stage,arcname='stage')
    manifest['archive_sha256']=sha(archive)
    mf=R/'e4_manifest_fixture.json';mf.write_text(json.dumps(manifest,indent=2)+'\n')
    root=R/'e4_sandbox';content=root/'content';content.mkdir(parents=True,exist_ok=False)
    payload={'e4_worker.py':'e4_worker.py','t15_stage.tar.gz':archive,'t15_manifest.json':mf,
             't15_budget.json':None}
    def upload():
        for name,src in payload.items():
            if src is None:(content/name).write_text(json.dumps({'mode':'fixture','work_deadline':time.time()+1800}))
            else:shutil.copyfile(R/src if isinstance(src,str) else src,content/name)
    wrapped,u=inject('upload',upload);retry('upload',wrapped)
    assert {x.name for x in content.iterdir()}==set(payload)
    print('PAYLOAD_ONLY',list(payload),flush=True)
    # Run EXACT worker copied from PAYLOAD, with only the compiled solver replaced by stub.
    stub=R/'e4_stub.py';log=root/'worker.log'
    with log.open('x') as f:
        p=subprocess.Popen([sys.executable,str(content/'e4_worker.py'),'--content',str(content),'--stub',str(stub)],cwd=content,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        try:
            def probe():
                o=content/'t15/out';return {x.name[:-7]:x.read_text().strip() for x in o.glob('*.sha256')}
            exec_probe,e=inject('exec',probe);poll,pr=inject('probe',lambda:retry('exec',exec_probe))
            download,d=inject('download',lambda name,target:shutil.copyfile(content/'t15/out'/name,target))
            cases=('dx1p0_s107','dx1p0_s108','dx1p0_s109')
            for case in cases:
                label='T15_'+case;hand=label+'_handoff.json';end=time.time()+1800
                while hand not in retry('probe',poll):
                    if p.poll() is not None:raise RuntimeError('worker stopped before '+case+'; inspect worker.log')
                    if time.time()>end:raise TimeoutError(case)
                    time.sleep(.2)
                local=root/'verified';local.mkdir(exist_ok=True)
                side=local/(hand+'.partial');retry('download',lambda:download(hand,side))
                handhash=probe()[hand]
                if sha(side)!=handhash:raise ValueError('handoff hash')
                side.replace(local/hand)
                hashes=json.loads((local/hand).read_text())['sha256']
                for n,h in hashes.items():
                    dst=local/n;retry('download',lambda n=n,dst=dst:download(n,dst))
                    sidecar=local/(n+'.sha256');retry('download',lambda n=n,sidecar=sidecar:download(n+'.sha256',sidecar))
                    if sha(dst)!=h or sidecar.read_text().strip()!=h:raise ValueError('hash '+n)
                ack=content/'t15/out'/(label+'.ack.json');ack.write_text(json.dumps(hashes))
                print('ACK_SHA_OK',case,len(hashes),flush=True)
            rc=p.wait(timeout=30)
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=10)
    assert rc==0,('worker failed',log)
    assert all(x[0] for x in (u,e,pr,d))
    assert (content/'t15/out/run.done').is_file()
    print('E4_TRANSPORT_FIXTURE_PASS 3 cases 4 injected timeouts, real worker/real build, stub solver, SHA ACK; NO GPU',flush=True)
if __name__=='__main__':main()
