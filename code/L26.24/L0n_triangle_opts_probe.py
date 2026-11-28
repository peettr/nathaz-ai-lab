import sys
sys.path[:0]=['/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0m/vendor','/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0m']
import numpy as np, triangle as tr
from l0m_generate import polygon_area
for seed in (1300000,1300001):
 r=np.random.default_rng(seed);t=int(r.integers(25000,67000));r.normal(size=(int(r.integers(40,121)),2))
 a=np.sort(r.uniform(0,2*np.pi,int(r.integers(8,13))));rad=r.uniform(.6,1.4,len(a));p=np.stack((rad*np.cos(a),rad*np.sin(a)),axis=1)
 n=len(p);lim=polygon_area(p)/(2*t);arg={'vertices':p,'segments':np.array([(i,(i+1)%n) for i in range(n)],np.int32)}
 for opts in (f'pq20a{lim:.12g}Q',f'pq20a{lim:.12f}Q',f'pqa{lim:.12f}Q',f'pq20a{lim:.12f}QY'):
  m=tr.triangulate(arg,opts)
  print(seed,opts,len(m.get('triangles',[])),len(m.get('vertices',[])),flush=True)
