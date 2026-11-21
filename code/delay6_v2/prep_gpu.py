import hashlib, os, sys, tarfile, time, traceback
from pathlib import Path
sys.path.insert(0, '/content/m7')
R=Path('/content/delay6')
def run():
    import full_m7 as m
    import requests
    p=R/'gfs_738_v1.tar.gz'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='0fb9df0b4c37842481c6811aa9a63f9a5c53e946d566a64b77f4a8026b76c671'
    with tarfile.open(p) as t:
        names=t.getnames()
        assert len(names)==739 and names[0]=='gfs' and all(n=='gfs' or n.startswith('gfs/') for n in names)
        assert all(x.isfile() or x.isdir() for x in t.getmembers())
        t.extractall(R,filter='data')
    assert len(list((R/'gfs').glob('*.npz')))==738
    print('RESTORED 738',flush=True)
    base='https://huggingface.co/linchensen/FuXi-CFD-model/resolve/98d2cb643ebddb752803919ad65eb2457314a2ae/fuxicfd-model/'
    for rel in ('model/fuxicfd_model.onnx','inference_example/normalization/scaler_input.npy','inference_example/normalization/scaler_output.npy'):
        out=m.ROOT/rel;out.parent.mkdir(parents=True,exist_ok=True)
        if not out.exists():
            res=requests.get(base+rel+'?download=true',stream=True,timeout=(30,120));res.raise_for_status()
            with out.open('xb') as f:
                for chunk in res.iter_content(1048576):f.write(chunk)
        print('STATIC',rel,out.stat().st_size,flush=True)
    model=m.ROOT/'model/fuxicfd_model.onnx'
    assert hashlib.sha256(model.read_bytes()).hexdigest()=='13daae67371d20a7ffb00db0a6c4679e580c28e77d2521eb7c2dcf9e80f20b3e'
    for site in m.SITES:m.dem(site)
    print('PREP_DONE',time.time(),flush=True)
if __name__=='__main__':
    try:run();(R/'prep.exit').write_text('0\n')
    except Exception:
        traceback.print_exc();(R/'prep.exit').write_text('1\n');raise
