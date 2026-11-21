"""Colab and local fixture entry points (only stdlib)."""
import hashlib,json,os,pathlib,re,subprocess,sys
C=pathlib.Path('/content')
def probe(c):
    o=c/'t9b17/out'; ready={}
    for s in sorted(o.glob('*.sha256')):
        p=o/s.name[:-7]
        if p.is_file():ready[p.name]={'sha':s.read_text().strip(),'size':p.stat().st_size}
    return ready

def ack(c,label):
    if not re.fullmatch(r'E_s10[12]_(?:on|off)',label):raise ValueError(label)
    (c/(label+'.ack.pending')).replace(c/'t9b17/out'/(label+'.ack.json'))

def launch(c):
    mark=c/'t9b17.launch'; receipt=c/'t9b17_upload.json'
    for n,h in json.loads(receipt.read_text()).items():
        if pathlib.Path(n).name!=n or hashlib.sha256((c/n).read_bytes()).hexdigest()!=h:raise ValueError(n)
    if not receipt.is_file() or json.loads((c/'t9b17_budget.json').read_text())['mode']!='production':raise ValueError('production only')
    with mark.open('x') as m,(c/'t9b17.log').open('x') as log:
        p=subprocess.Popen([sys.executable,str(c/'worker_gate.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        m.write(str(p.pid));print('LAUNCHED',p.pid,flush=True)
