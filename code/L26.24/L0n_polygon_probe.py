import sys,time
from pathlib import Path
sys.path[:0]=['/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0m/vendor','/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0m']
import numpy as np
import triangle as tr
from scipy.spatial import ConvexHull
from l0m_generate import polygon_area

def cross(a,b,c): return np.cross(b-a,c-a)
def intersects(a,b,c,d):
    return cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0
for seed in range(1300000,1300005):
    t=time.monotonic();rng=np.random.default_rng(seed);target=int(rng.integers(25000,67000))
    outer=rng.normal(size=(int(rng.integers(40,121)),2));outer=outer[ConvexHull(outer).vertices]
    angles=np.sort(rng.uniform(0,2*np.pi,int(rng.integers(8,13))))
    radii=rng.uniform(.6,1.4,len(angles))
    outer=np.stack((radii*np.cos(angles),radii*np.sin(angles)),axis=1)
    n=len(outer);area=polygon_area(outer);limit=area/(2*target)
    crossings=sum(intersects(outer[i],outer[(i+1)%n],outer[j],outer[(j+1)%n]) for i in range(n) for j in range(i+2,n) if (j+1)%n!=i)
    args={'vertices':outer,'segments':np.asarray([(i,(i+1)%n) for i in range(n)],np.int32)}
    m=tr.triangulate(args,f'pq20a{limit:.12g}Q')
    coords=np.asarray(m.get('vertices',[]));faces=np.asarray(m.get('triangles',[]))
    if len(faces):
        from skfem import MeshTri,Basis,ElementTriP1
        mesh=MeshTri(coords.T,faces.T);basis=Basis(mesh,ElementTriP1());interior=basis.N-len(basis.get_dofs().all())
    else:interior=None
    print(dict(seed=seed,vertices=n,area=area,self_intersections=crossings,target=target,area_limit=limit,triangles=len(faces),total_vertices=len(coords),interior=interior,seconds=time.monotonic()-t),flush=True)
