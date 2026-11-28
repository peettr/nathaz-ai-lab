"""Recompute B2 from returned rank0/cp/gate without changing frozen files."""
import gzip, json, pathlib, re, statistics, sys
P=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else pathlib.Path(__file__).parent/'returned')
F=('Ux','Uy','Uz','p','k','omega')
rank0=sorted(P.glob('B2_*_rank0.gz'))
if not rank0:
    print('NO_B2_RETURNED_RANK0');sys.exit(2)
r=rank0[-1]; pre=r.name.removesuffix('_rank0.gz')
with gzip.open(r,'rt',errors='replace') as f:t=f.read()
a={f:[float(x) for x in re.findall(r'Solving for '+f+r', Initial residual = ([0-9.eE+-]+)',t)] for f in F}
if any(not x for x in a.values()):print('INCOMPLETE_RESIDUALS',{f:len(x) for f,x in a.items()});sys.exit(3)
assert len(a['p'])==3*len(a['Ux']), 'Unexpected p correctors per step'
a['p']=a['p'][0::3]
print('source',r,'counts',{f:len(x) for f,x in a.items()})
print('residual last/first (p first correction per step)',{f:x[-1]/x[0] for f,x in a.items()})
p=a['p']; print('p last2000 block500 means',[statistics.mean(p[i:i+500]) for i in range(len(p)-2000,len(p),500)])
cpfile=P/(pre+'_cp_trace.gz')
if cpfile.exists():
 with gzip.open(cpfile,'rt') as f:cp=[float(l.split(',')[1]) for l in f.read().splitlines()[1:]]
 print('cp samples',len(cp),'last',cp[-1],'last500mean',statistics.mean(cp[-500:]),'gate_change',abs(cp[-1]-cp[-500])/abs(cp[-500]),'peak_to_peak_last1000',(max(cp[-1000:])-min(cp[-1000:]))/abs(statistics.mean(cp[-1000:])))
y=re.findall(r'patch roof y\+ : min = ([0-9.eE+-]+), max = ([0-9.eE+-]+), average = ([0-9.eE+-]+)',t)
print('roof yplus',y[-1] if y else 'MISSING')
g=P/(pre+'_primal_gate.gz')
if g.exists():
 with gzip.open(g,'rt') as f:j=json.load(f)
 print('gate',j)
