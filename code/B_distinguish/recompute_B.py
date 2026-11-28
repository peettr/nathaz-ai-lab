"""L26.21 G1 recompute from archived returned files (Lead, 11-14). Usage: python3 recompute_g1.py <dir>"""
import gzip,re,sys,json,numpy as np,pathlib
d=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else '.')
F=['Ux','Uy','Uz','p','k','omega']
def rd(p): return gzip.open(p,'rt',errors='replace').read()
runs={'B1':'B_distinguish__coarse_0001','B2':'B_distinguish__B2_0001'}
for name,pre in runs.items():
    candidates=sorted(d.glob('B_distinguish__'+('coarse' if name=='B1' else 'B2')+'_????_rank0.gz'));
    if not candidates: print('MISSING',name); continue
    pre=candidates[-1].name[:-len('_rank0.gz')]; r=rd(candidates[-1]); print('==',name,pre)
    for f in F:
        v=np.array([float(x) for x in re.findall(r'Solving for %s, Initial residual = ([0-9.eE+-]+)'%f,r)])
        print(f' {f}: n={len(v)} last/first={v[-1]/v[0]:.3e} decades={-np.log10(v[-1]/v[0]):.2f}')
    p=np.array([float(x) for x in re.findall(r'Solving for p, Initial residual = ([0-9.eE+-]+)',r)])
    blocks=[(a,a+500) for a in range(3000,5000,500)]
    print(' p initial residual, 500-step block means (steps 3001-5000):',' '.join(f'{p[a:b].mean():.4e}' for a,b in blocks))
    print(' p last2000 min/max: %.3e / %.3e'%(p[-2000:].min(),p[-2000:].max()))
    sl=np.polyfit(np.arange(2000),p[-2000:],1)[0]*2000/p[-2000:].mean()
    print(' p last2000 linear-trend change over window / mean: %.2e'%sl)
    yp=re.findall(r'patch roof y\+ : min = ([0-9.]+), max = ([0-9.]+), average = ([0-9.]+)',r)
    if yp: print(' roof y+ min/max/avg:',yp[-1])
    cpf=d/(pre+'_cp_trace.gz')
    if cpf.exists():
        cp=np.array([float(l.split(',')[1]) for l in rd(cpf).splitlines()[1:]]); w=cp[-500:]
        print(' Cp samples',len(cp),' Cp_final=%.5f  mean(last500)=%.5f'%(cp[-1],w.mean()))
        print(' gate metric |Cp[-1]-Cp[-500]|/|Cp[-500]| = %.3e'%(abs(cp[-1]-cp[-500])/abs(cp[-500])))
        print(' peak-to-peak(last500)/|mean| = %.3e ; peak-to-peak(last1000)/|mean| = %.3e'%((w.max()-w.min())/abs(w.mean()),(cp[-1000:].max()-cp[-1000:].min())/abs(cp[-1000:].mean())))
    g=d/(pre+'_primal_gate.gz')
    if g.exists(): j=json.loads(rd(g)); print(' gate json: u_ref=%s primal_gate=%s cp_last500_change=%s'%(j['u_ref'],j['primal_gate'],j['cp_last500_change']))
