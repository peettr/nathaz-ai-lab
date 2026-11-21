#!/usr/bin/env python3
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
import controller as c
import remote_io as io

def trial(sandbox,n,target):
    content=sandbox/n/'content';content.mkdir(parents=True)
    retained=c.R/'local_evidence'/n;retained.mkdir(parents=True)
    for p in c.PAYLOAD:
        if p!=c.PAYLOAD[-1]:shutil.copyfile(c.R/p,content/p)
        else:(content/p).write_text(json.dumps(dict(mode='local-fixture',work_deadline=time.time()+220,fixture_off_sha=target)))
    assert {p.name for p in content.iterdir()}==set(c.PAYLOAD);print('PAYLOAD_ONLY',n,*sorted(c.PAYLOAD),flush=True)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(sandbox)}
    with (retained/'real_worker.log').open('x') as log:
        proc=subprocess.Popen([sys.executable,str(content/'worker_gate.py'),'--content',str(content),'--stub',str(c.R/'dry_stub.py')],cwd=content,stdout=log,stderr=subprocess.STDOUT,env=env)
        try:
            def download(name,out):shutil.copyfile(content/'t9b17/out'/name,out)
            def publish(label,values):
                (content/(label+'.ack.pending')).write_text(json.dumps(values));io.ack(content,label)
            result=c.collect(retained,lambda:io.probe(content),download,publish,time.time()+210,'local-fixture')
            rc=proc.wait(timeout=8)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=8)
    print((retained/'real_worker.log').read_text(),end='',flush=True);print('TRIAL',n,result,rc,flush=True)
    assert not list(retained.glob('*.vtk'))
    return result,rc,retained

def main():
    with tempfile.TemporaryDirectory(prefix='t9b17_') as tmp:
        sb=pathlib.Path(tmp)
        result,rc,red=trial(sb,'gate1_red','0'*64)
        assert result=='failed' and rc!=0 and 'city gate failed at E_s101_off' in (red/'run.failed').read_text()
        assert not (red/'E_s101_on_solver.log').exists()
        target=c.sha(red/'E_s101_off_points80.json')
        result,rc,green=trial(sb,'all_three_green',target)
        assert result=='done' and rc==0
        for i,label in enumerate(c.CASES):
            rows=json.loads((green/f'{label}_points80.json').read_text())['rows']
            assert all(abs(r['Su']-(i+1))<1e-12 and r['fluid_corners']==8 for r in rows)
            m=json.loads((green/f'{label}_fluid_mask.json').read_text())
            assert m['solid_cells']==3 and m['mask_sha256']==hashlib.sha256(bytes(3)+b'\1'*999997).hexdigest()
        assert json.loads((green/'gate3.json').read_text())['passed']
        d=json.loads((green/'points80_difference.json').read_text());assert d['count']==80 and abs(d['max_abs_delta_Su']-1)<1e-12
        assert all(c.sha(path.with_name(path.name[:-7]))==path.read_text().strip() for path in green.glob('*.sha256'))
    print('PASS real worker; negative gate1 and three-case positive path; copied compact evidence and ACKed every executed case; no GPU, no Colab',flush=True)

if __name__=='__main__':main()
