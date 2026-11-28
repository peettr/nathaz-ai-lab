#!/usr/bin/env python3
"""Input-only audit of TInF's E=componentwise Lund^2/R-row (NOT Cholesky)."""
import argparse,json,re
from pathlib import Path
import numpy as np
NUM=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'
def read(p,n):
    return np.array([list(map(float,re.findall(NUM,s))) for s in p.read_text().splitlines() if s.lstrip().startswith('(') and len(re.findall(NUM,s))==n])
def main():
    p=argparse.ArgumentParser();p.add_argument('boundary',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    points=read(a.boundary/'points',3);rs=read(a.boundary/'R',6);ls=read(a.boundary/'L',9)
    if tuple(map(len,(points,rs,ls)))!=(164,164,164): raise ValueError('expected 164 U/R/L points')
    eigen=[];negative=[];degenerate=[]
    for i,(point,r,l) in enumerate(zip(points,rs,ls)):
        xx,xy,xz,yy,yz,zz=r
        R=np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]])
        eigen.append(float(np.linalg.eigvalsh(R)[0]))
        if eigen[-1]<=0:continue
        B=np.linalg.cholesky(R)
        E=B*B/np.array([xx,yy,zz])[:,None]
        if abs(np.linalg.det(E))<1e-14:degenerate.append(i);continue
        L0=np.linalg.solve(E,l.reshape(3,3))
        for row,col in np.argwhere(L0<0):negative.append({'input_index_0based':i,'z_m':float(point[2]),'row':int(row),'col':int(col),'value':float(L0[row,col])})
    out={'source_definition':'TInF turbulentDFMInlet: E=cmptMultiply(Lund,Lund) row divided by R.xx/R.yy/R.zz; L0=inv(E)&L; Lund=lower Cholesky(R)', 'input_points':164,'R_all_positive_definite':min(eigen)>0,'minimum_R_eigenvalue':min(eigen),'R_nonpositive_indices':[i for i,e in enumerate(eigen) if e<=0],'E_degenerate_indices':degenerate,'E_inverse_L_negative_entries':negative,'negative_count':len(negative)}
    if a.output.exists():raise FileExistsError(a.output)
    a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'input_points':164,'R_positive':out['R_all_positive_definite'],'negative_count':len(negative),'output':str(a.output)}))
if __name__=='__main__':main()
