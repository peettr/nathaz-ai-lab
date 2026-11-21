"""L26.21 B1 archived snapshot recomputation; snapshots are not separate runs."""
import gzip, json, pathlib, re, statistics
P=pathlib.Path(__file__).parent/'returned'
F=('Ux','Uy','Uz','p','k','omega')
def rd(p):
    with gzip.open(p,'rt',errors='replace') as fp: return fp.read()
for i in (1,2,3):
    pre=f'coarse_{i:04d}'
    t=rd(P/f'{pre}_rank0.gz')
    j=json.loads(rd(P/f'{pre}_primal_gate.gz'))
    arrays={f:[float(x) for x in re.findall(r'Solving for '+f+r', Initial residual = ([0-9.eE+-]+)',t)] for f in F}
    cp=[float(l.split(',')[1]) for l in rd(P/f'{pre}_cp_trace.gz').splitlines()[1:]]
    yp=re.findall(r'patch roof y\+ : min = ([0-9.eE+-]+), max = ([0-9.eE+-]+), average = ([0-9.eE+-]+)',t)
    print('snapshot',pre,'step-counts',{f:len(x) for f,x in arrays.items()},'gate',j['primal_gate'])
    p0=arrays['p']; assert len(p0)==3*len(arrays['Ux']), 'unexpected pressure corrector count'; arrays['p']=p0[0::3]
    print('ratio-last-first (p: first correction each step)',{f:arr[-1]/arr[0] for f,arr in arrays.items()})
    p=arrays['p']; print('p last2000-step means', [statistics.mean(p[k:k+500]) for k in range(len(p)-2000,len(p),500)])
    if len(p0)==15000:
        ps=p0[::3]; pl=p0[2::3]
        print('p-first-corrector 500-step means last2000',[statistics.mean(ps[k:k+500]) for k in range(3000,5000,500)])
        print('p-last-corrector 500-step means last2000',[statistics.mean(pl[k:k+500]) for k in range(3000,5000,500)])
    print('cp-last',cp[-1],'last500mean',statistics.mean(cp[-500:]),'gate-change',abs(cp[-1]-cp[-500])/abs(cp[-500]),'peakpeak-last1000',(max(cp[-1000:])-min(cp[-1000:]))/abs(statistics.mean(cp[-1000:])))
    print('roof-yplus',yp[-1] if yp else 'unavailable')
    print('progress',rd(P/f'{pre}_progress.gz'))
