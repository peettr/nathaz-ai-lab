#!/usr/bin/env python3
"""PAYLOAD-only real worker + one timeout per transport class; no Colab."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
import controller as c
import remote_io as io
R=pathlib.Path(__file__).resolve().parent
real_sleep=c.time.sleep
c.time.sleep=lambda secs:real_sleep(min(secs,0.005))
def once(label,fn):
    fired=False
    def call(*a,**k):
        nonlocal fired
        if not fired:
            fired=True;print('INJECT_TIMEOUT',label,flush=True);raise OSError('timeout')
        return fn(*a,**k)
    return call

def main():
    with tempfile.TemporaryDirectory(prefix='t13-run2-dry-',dir=os.environ.get('TMPDIR')) as temp:
        content=pathlib.Path(temp)/'content';content.mkdir()
        out=R/'local_injected_dry_t13_sealed';out.mkdir(exist_ok=False)
        def transfer():
            for n in c.PAYLOAD:
                if n=='t13_budget.json':(content/n).write_text(json.dumps({'mode':'fixture','work_deadline':time.time()+900}))
                else:shutil.copyfile(R/n,content/n)
        c.retry_step('upload fixture PAYLOAD',once('upload',transfer),time.time()+850)
        assert {p.name for p in content.iterdir()}==set(c.PAYLOAD)
        print('PAYLOAD_ONLY',sorted(c.PAYLOAD),flush=True)
        with (out/'worker.log').open('x') as log:
            p=subprocess.Popen([sys.executable,str(content/'worker.py'),'--content',str(content),'--stub',str(R/'dry_stub.py')],cwd=content,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            try:
                def exec_probe():return io.probe(content)
                def probe():return c.retry_step('exec probe',once_exec(),time.time()+850)
                fired=[False,False]
                def once_exec():
                    def call():
                        if not fired[0]:
                            fired[0]=True;print('INJECT_TIMEOUT','exec',flush=True);raise OSError('timeout')
                        if not fired[1]:
                            fired[1]=True;print('INJECT_TIMEOUT','probe',flush=True);raise OSError('timeout')
                        return exec_probe()
                    return call
                def download(n,dest):
                    c.retry_step('download '+n,once_download(n,dest),time.time()+850)
                hit=[False]
                def once_download(n,dest):
                    def call():
                        if not hit[0]:
                            hit[0]=True;print('INJECT_TIMEOUT','download',flush=True);raise OSError('timeout')
                        shutil.copyfile(content/'t13/out'/n,dest)
                    return call
                def publish(label,hashes):
                    (content/(label+'.ack.pending')).write_text(json.dumps(hashes));io.ack(content,label)
                result=c.collect(out,probe,download,publish,time.time()+850,'fixture')
                rc=p.wait(timeout=8)
            finally:
                if p.poll() is None:p.terminate();p.wait(timeout=8)
        print('DRY_RESULT',result,rc,flush=True)
        assert result=='done' and rc==0
        for label in c.CASES:
            assert len(json.loads((out/(label+'_points80.json')).read_text())['rows'])==80
        assert all(c.sha(p.with_name(p.name[:-7]))==p.read_text().strip() for p in out.glob('*.sha256'))
        assert all(fired) and hit[0]
    print('REAL_WORKER_INJECTED_PASS: two cases, points80, slices, SHA, ACK; 4 injected transport timeouts; no GPU',flush=True)
if __name__=='__main__':main()
