#!/usr/bin/env python3
"""CRC preflight of the 164 fixed input tensors; no solver run."""
import argparse,json,re
from pathlib import Path
import numpy as np
NUM=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'
def read(f,n):
    return np.array([list(map(float,re.findall(NUM,l))) for l in f.read_text().splitlines() if len(re.findall(NUM,l))==n and l.strip()!='164'])
def main():
    p=argparse.ArgumentParser();p.add_argument('boundary',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
    pts=read(a.boundary/'points',3); R=read(a.boundary/'R',6); L=read(a.boundary/'L',9)
    if (len(pts),len(R),len(L))!=(164,164,164):raise ValueError('input count is not 164')
    mins=[]; negatives=[]
    for i,(r,l) in enumerate(zip(R,L)):
        rm=np.array([[r[0],r[1],r[2]],[r[1],r[3],r[4]],[r[2],r[4],r[5]]]);eig=np.linalg.eigvalsh(rm);mins.append(float(eig.min()))
        if eig.min()<=0: continue
        E=np.linalg.cholesky(rm)
        transformed=np.linalg.solve(E,l.reshape(3,3))
        for j,k in np.argwhere(transformed<0): negatives.append({'index_0based':i,'z':float(pts[i,2]),'row':int(j),'col':int(k),'value':float(transformed[j,k])})
    out={'points':len(pts),'R_all_positive_definite':bool(min(mins)>0),'min_R_eigenvalue':min(mins),
         'nonpositive_R_indices':[i for i,v in enumerate(mins) if v<=0],
         'E_inverse_L_definition':'E=lower Cholesky(R); solve(E,L) at each input point',
         'E_inverse_L_negative_entries':negatives,'negative_count':len(negatives)}
    if a.out.exists():raise FileExistsError(a.out)
    a.out.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'out':str(a.out),'points':out['points'],'R_positive':out['R_all_positive_definite'],'negative_count':out['negative_count']}))
if __name__=='__main__':main()
