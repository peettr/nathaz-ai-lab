#!/usr/bin/env python3
"""Create review-compliant, versioned G1 mesh inputs without altering v1."""
from pathlib import Path
import shutil, math, re
base=Path(__file__).resolve().parent
out=base/'review_v3'
assert not out.exists(), out
for grade,(nx,ny,nz) in {'coarse':(80,48,38),'medium':(130,70,50)}.items():
    src=base/'cases'/grade; dst=out/'cases'/grade
    shutil.copytree(src,dst)
    bm=dst/'system/blockMeshDict'
    s=bm.read_text();s,n=re.subn(r'\(\d+ \d+ \d+\) simpleGrading \(1 1 1\)',f'({nx} {ny} {nz}) simpleGrading (1 1 8)',s)
    assert n==1; s=s.replace('top { type symmetryPlane;', 'top { type patch;')
    bm.write_text(s)
    r=8**(1/(nz-1)); first=64*(r-1)/(r**nz-1)
    heights=[];z=0
    for i in range(nz):
        h=first*r**i;heights.append(h);z+=h
    assert first<=.5 and r<=1.2 and sum(1 for i,h in enumerate(heights) if sum(heights[:i+1])<=8)>=10
    assert abs(z-64)<1e-8
    (dst/'vertical_grading.txt').write_text(f'nz={nz} ratio={r:.8f} first={first:.8f} layers_below_H={sum(1 for i in range(nz) if sum(heights[:i+1])<=8)}\n')
    for name in ('U','k','omega','p','nut'):
        f=dst/'0'/name;s=f.read_text()
        if name in ('U','k','omega'):
            kappa=.41;z0=.03;ustar=kappa*10/math.log((8+z0)/z0); cmu=.09
            value={'U':f'({ustar/kappa*math.log((64+z0)/z0):.12g} 0 0)',
                   'k':f'{ustar**2/math.sqrt(cmu):.12g}',
                   'omega':f'{ustar/(kappa*math.sqrt(cmu)*(64+z0)):.12g}'}[name]
            top=f'top {{type fixedValue; value uniform {value};}}'
        else: top='top {type zeroGradient;}'
        assert s.count('"(sideNeg|sidePos|top)" {type symmetryPlane;}')==1
        s=s.replace('"(sideNeg|sidePos|top)" {type symmetryPlane;}',f'"(sideNeg|sidePos)" {{type symmetryPlane;}}\n {top}')
        f.write_text(s)
    print(grade,nx*ny*nz,(dst/'vertical_grading.txt').read_text().strip())
print(out)
