"""Colab and local fixture entry points (only stdlib)."""
import hashlib,json,os,pathlib,re,subprocess,sys
C=pathlib.Path('/content')
def probe(c):
    o=c/'t13b/out'; ready={}
    for s in sorted(o.glob('*.sha256')):
        p=o/s.name[:-7]
        if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
    return ready

def ack(c,label):
    if not re.fullmatch(r'E_s10[12]_off',label):raise ValueError(label)
    (c/(label+'.ack.pending')).replace(c/'t13b/out'/(label+'.ack.json'))

def launch(c):
    mark=c/'t13b.launch'; receipt=c/'t13_upload.json'
    for n,h in json.loads(receipt.read_text()).items():
        if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError(n)
    if not receipt.is_file() or json.loads((c/'t13b_budget.json').read_text())['mode']!='production':raise ValueError('production only')
    if mark.exists():
        pid=mark.read_text().strip()
        if not pid:raise OSError('launch marker exists but PID not yet committed')
        print('ALREADY_LAUNCHED',pid,flush=True)
        return
    with mark.open('x') as m,(c/'t13b.log').open('x') as log:
        p=subprocess.Popen([sys.executable,str(c/'worker.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        m.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
