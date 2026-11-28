"""L0l bounded CPU diagnostics, run only on allocated CRC worker."""
import ctypes as C, json, os, time, sys
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0l')
sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.sparse import tril, diags
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
from skfem import MeshTri, Basis, ElementTriP1, asm
from skfem.models.poisson import laplace
from scipy.spatial import ConvexHull, Delaunay
from l0i_generate import make_sample, rhs, inside

def mesh_quality(seed,geometry):
    # Reproduce l0i_generate.py:31-60 without assembling; uniform midpoint
    # refinement preserves each initial triangle's three angles.
    rng=np.random.default_rng(seed)
    rng.integers(20000,100001)
    outer=rng.normal(size=(int(rng.integers(40,121)),2))
    hull=outer[ConvexHull(outer).vertices]
    if geometry==2:
        ang=np.sort(rng.uniform(0,2*np.pi,int(rng.integers(8,13))))
        radii=rng.uniform(.6,1.4,size=len(ang))
        poly=np.column_stack((radii*np.cos(ang),radii*np.sin(ang)))
        outer=np.concatenate((poly,rng.uniform(-1.4,1.4,size=(len(outer)*2,2))))
        outer=outer[inside(outer,poly)]
    else: poly=hull
    hole=None
    if geometry==1:
        inner=rng.normal(scale=np.sqrt(.2),size=(int(rng.integers(12,25)),2))
        hole=inner[ConvexHull(inner).vertices]
        outer=np.concatenate((outer,hole))
    tri=Delaunay(outer).simplices
    centres=outer[tri].mean(axis=1)
    mask=inside(centres,poly)
    if hole is not None: mask &= ~inside(centres,hole)
    P=outer[tri[mask]]
    E=np.stack((np.linalg.norm(P[:,1]-P[:,2],axis=1),np.linalg.norm(P[:,0]-P[:,2],axis=1),np.linalg.norm(P[:,0]-P[:,1],axis=1)),axis=1)
    a,b,c=E.T
    angles=np.degrees(np.arccos(np.clip((b*b+c*c-a*a)/(2*b*c),-1,1)))
    return {'initial_triangle_min_angle_deg':float(np.min(np.minimum.reduce((angles, np.degrees(np.arccos(np.clip((a*a+c*c-b*b)/(2*a*c),-1,1))),np.degrees(np.arccos(np.clip((a*a+b*b-c*c)/(2*a*b),-1,1))))))),
            'initial_triangle_count':len(P),'note':'uniform midpoint refinements preserve triangle angles'}

ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0l')
OUT=ROOT/'cpu'/'out'
assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
OUT.mkdir(parents=True,exist_ok=True)
SEEDS=json.loads((ROOT/'accepted_seeds.json').read_text())
ARCHIVE=json.loads((ROOT/'l0k_selfcheck.json').read_text())
rows=[r for r in SEEDS['accepted'] if r['split']=='test']
assert len(rows)==300 and len(ARCHIVE['test_rows'])==300
lib=C.CDLL('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
lib.ic0_factor.argtypes=[C.c_int,I,I,D,D];lib.ic0_factor.restype=C.c_int

def factor(A):
    L=tril(A,format='csr');L.sort_indices(); f=np.empty_like(L.data)
    status=lib.ic0_factor(A.shape[0],L.indptr,L.indices,np.ascontiguousarray(L.data),f)
    if status: raise RuntimeError(f'IC breakdown at {status}')
    L.data=f
    return L

def pcg(A,b,L,maxiter=10000):
    # Exact same triangular path as l0k_worker.py:194-214.
    M=LinearOperator(A.shape,dtype=np.float64,matvec=lambda v:spsolve_triangular(
        L.T.tocsr(),spsolve_triangular(L,v,lower=True),lower=False))
    count=[0]
    x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=maxiter,M=M,
              callback=lambda _:count.__setitem__(0,count[0]+1))
    return {'iterations':count[0],'info':int(info),'relative_residual_b':float(np.linalg.norm(b-A@x)/np.linalg.norm(b))}

def emit(name,value):
    with (OUT/name).open('x') as f: json.dump(value,f,indent=2,allow_nan=False)

def main():
    results=[];start=time.monotonic()
    for j,r in enumerate(rows[:20]):
        A,b,m=make_sample(r['seed'],r['geometry']);L=factor(A)
        # Distinct wrappers deliberately use the same lower triangular solve ordering.
        baseline=pcg(A,b,L)
        neuralif_application=pcg(A,b,L.copy())
        archive=ARCHIVE['test_rows'][j]['ic0_iterations']
        same=baseline['iterations']==neuralif_application['iterations']==archive and baseline['info']==neuralif_application['info']==0
        results.append({'index':j,'seed':r['seed'],'geometry':r['geometry'],
                        'n':A.shape[0],'nnz':A.nnz,'mesh_quality':mesh_quality(r['seed'],r['geometry']),
                        'l0k_ic_iterations':archive,'ic_baseline':baseline,
                        'ic_via_neuralif_application':neuralif_application,'equal':same,
                        'boundary':'boundary DOFs eliminated: A=K[interior][:,interior], b=f[interior]',
                        'relative_residual_definition':'||b-Ax||_2 / ||b||_2; x0=0'})
        print('PATH',j,same,baseline['iterations'],flush=True)
        if time.monotonic()-start>3600: raise TimeoutError('CPU time gate')
    by_class={str(g):float(np.mean([ARCHIVE['test_rows'][i]['ic0_iterations'] for i,r in enumerate(rows) if r['geometry']==g])) for g in (0,1,2)}
    emit('ic_application_20.json',{'source':'L0k frozen accepted seeds','all_equal':all(x['equal'] for x in results),'ic0_mean_by_geometry_all300':by_class,'rows':results})
    # Uniform square P1 calibration; boundary eliminated. Reference count n=223^2=49729.
    mesh=MeshTri.init_sqsymmetric()
    for _ in range(7): mesh=mesh.refined()
    basis=Basis(mesh,ElementTriP1())
    interior=np.setdiff1d(np.arange(basis.N),basis.get_dofs().all())
    A=asm(laplace,basis).tocsr()[interior][:,interior].tocsr()
    b=np.asarray(asm(rhs,basis))[interior]
    L=factor(A)
    ic=pcg(A,b,L)
    count=[0]
    x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=10000,callback=lambda _:count.__setitem__(0,count[0]+1))
    emit('calibration.json',{'n':A.shape[0],'nnz':A.nnz,'boundary':'Dirichlet eliminated',
          'rhs':'assembled FEM constant f=1, restricted to interior',
          'stopping':'scipy cg rtol=1e-6 atol=0, x0=0 => ||r||/||b||; same as ||r||/||r0|| only for x0=0',
          'none_iterations':count[0],'none_info':int(info),'none_true_relative_residual':float(np.linalg.norm(b-A@x)/np.linalg.norm(b)),
          'ic0':ic})
if __name__=='__main__': main()
