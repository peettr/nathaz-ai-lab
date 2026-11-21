"""L0m reconstructed FEM data; NOT authors' original geometry/mesh.
Triangle 20250106 quality PSLG q20, no network, reject invalid candidates.
"""
import numpy as np
import triangle as tr
from scipy.spatial import ConvexHull
from skfem import MeshTri, Basis, ElementTriP1, asm
from skfem.models.poisson import laplace, unit_load


def polygon_area(p):
    return abs(np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1))) / 2


def min_angle(p, t):
    v = p[t]
    a = np.linalg.norm(v[:, 1] - v[:, 2], axis=1)
    b = np.linalg.norm(v[:, 0] - v[:, 2], axis=1)
    c = np.linalg.norm(v[:, 0] - v[:, 1], axis=1)
    if np.any(np.minimum.reduce((a,b,c)) <= 0): return 0.
    angles = [np.arccos(np.clip((b*b+c*c-a*a)/(2*b*c), -1, 1)),
              np.arccos(np.clip((a*a+c*c-b*b)/(2*a*c), -1, 1)),
              np.arccos(np.clip((a*a+b*b-c*c)/(2*a*b), -1, 1))]
    return float(np.rad2deg(np.min(angles)))


def build(seed, geometry, assemble=True):
    assert geometry in (0,1,2)
    rng = np.random.default_rng(int(seed))
    target = int(rng.integers(25000, 67000))  # assumption; n/nnz checked after assembly
    outer = rng.normal(size=(int(rng.integers(40,121)),2))
    outer = outer[ConvexHull(outer).vertices]
    if geometry == 2:
        angles = np.sort(rng.uniform(0, 2*np.pi, int(rng.integers(8,13))))
        radii = rng.uniform(.6,1.4,len(angles))
        outer = np.stack((radii*np.cos(angles), radii*np.sin(angles)),axis=1)
    inner = None
    if geometry == 1:
        samples = rng.normal(scale=np.sqrt(.2),size=(int(rng.integers(12,25)),2))
        inner = samples[ConvexHull(samples).vertices]
        from matplotlib.path import Path
        if not np.all(Path(outer).contains_points(inner)): raise ValueError('hole outside outer polygon')
    polys = [outer] + ([inner] if inner is not None else [])
    points = np.concatenate(polys)
    seg = []; offset=0
    for poly in polys:
        seg.extend((offset+i,offset+(i+1)%len(poly)) for i in range(len(poly)))
        offset += len(poly)
    area = polygon_area(outer) - (polygon_area(inner) if inner is not None else 0.)
    if area <= 0: raise ValueError('degenerate polygon')
    args={'vertices':points,'segments':np.asarray(seg,dtype=np.int32)}
    if inner is not None: args['holes']=inner.mean(axis=0).reshape(1,2)
    # area control; reject rather than alter the prescribed mesh after seeing scores
    # Triangle's option parser does not accept scientific notation for -a;
    # 2.2e-05 was parsed as an ineffective area constraint (L0m polygon failure).
    # Triangle's realized interior count exceeds this target under quality refinement;
    # using area/target instead of area/(2*target) keeps accepted nnz under 500k.
    area_limit=area/target
    assert area_limit >= 1e-12
    meshdata=tr.triangulate(args,f'pq20a{area_limit:.12f}Q')
    if 'triangles' not in meshdata: raise ValueError('triangle returned no triangles')
    coords=np.asarray(meshdata['vertices'],dtype=np.float64)
    faces=np.asarray(meshdata['triangles'],dtype=np.int32)
    angle=min_angle(coords,faces)
    if angle < 19.99: raise ValueError(f'min_angle={angle:.5f}<20')
    mesh=MeshTri(coords.T,faces.T)
    basis=Basis(mesh,ElementTriP1())
    interior=np.setdiff1d(np.arange(basis.N),basis.get_dofs().all())
    n=len(interior)
    if not 20000<=n<=100000: raise ValueError(f'n={n} out of range')
    # P1 triangular adjacency upper bound before assembly; actual nnz checked later.
    if len(faces)*6+len(coords)>700000: raise ValueError('mesh too large before assembly')
    A=asm(laplace,basis).tocsr()[interior][:,interior].tocsr()
    A.sum_duplicates(); A.sort_indices()
    if A.nnz>500000: raise ValueError(f'nnz={A.nnz}>500000')
    if not np.all(np.isfinite(A.data)) or np.any(A.diagonal()<=0): raise ValueError('invalid stiffness')
    meta={'seed':int(seed),'geometry':int(geometry),'target_n':target,'n':n,'nnz':int(A.nnz),
          'min_angle_deg':angle,'total_vertices':len(coords),'triangles':len(faces),
          'mesh':'triangle-20250106 pq20 area constrained', 'boundary':'eliminated Dirichlet'}
    if not assemble: return meta
    b=np.asarray(asm(unit_load,basis))[interior]
    return A,b,meta

make_sample=build
