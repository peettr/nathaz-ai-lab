"""L26.24 L0b: frozen, independently reconstructed Poisson P1 sample.
Source: Haeusner et al. TMLR 2024 App A.2 PDF p.19; all unspecified
choices are explicitly frozen in L0b_参数来源表.md. Never an author sample.
"""
import numpy as np
from scipy.spatial import ConvexHull, Delaunay
from scipy.sparse import issparse
from skfem import MeshTri, Basis, ElementTriP1, asm, BilinearForm, LinearForm
from skfem.helpers import dot, grad

@BilinearForm
def laplace(u, v, w):
    return dot(grad(u), grad(v))

@LinearForm
def rhs(v, w):
    return v

def inside(points, poly):
    # Ray-crossing for non-self-intersecting polygon; includes boundary fuzz.
    x, y = points.T
    hit = np.zeros(len(points), dtype=bool)
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):
        crossing = (a[1] > y) != (b[1] > y)
        xcut = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1] + 1e-300) + a[0]
        hit ^= crossing & (x < xcut)
    return hit

def make_sample(seed, geometry, sensitivity=False):
    assert geometry in (0, 1, 2)
    rng = np.random.default_rng(seed)
    target = int(rng.integers(20000, 100001))
    outer = rng.normal(size=(int(rng.integers(40, 121)), 2))
    hull = outer[ConvexHull(outer).vertices]
    if geometry == 2:
        # Simple radial polygon, cyclic angles imply no self-intersection.
        ang = np.sort(rng.uniform(0, 2*np.pi, int(rng.integers(8, 13))))
        radii = rng.uniform(.6, 1.4, size=len(ang))
        poly = np.column_stack((radii*np.cos(ang), radii*np.sin(ang)))
        outer = np.concatenate((poly, rng.uniform(-1.4, 1.4, size=(len(outer)*2, 2))))
        keep = inside(outer, poly)
        outer = outer[keep]
    else:
        poly = hull
    hole = None
    if geometry == 1:
        inner = rng.normal(scale=np.sqrt(.2), size=(int(rng.integers(12, 25)), 2))
        hole = inner[ConvexHull(inner).vertices]
        outer = np.concatenate((outer, hole))
    tri = Delaunay(outer).simplices
    centres = outer[tri].mean(axis=1)
    mask = inside(centres, poly)
    if hole is not None:
        mask &= ~inside(centres, hole)
    tri = tri[mask]
    if not len(tri):
        raise ValueError('empty triangulation')
    used, compact = np.unique(tri, return_inverse=True)
    mesh = MeshTri(outer[used].T, compact.reshape(-1, 3).T)
    # Bounded uniform refinements. Never downsample or silently change target.
    best = None
    for level in range(8):
        basis = Basis(mesh, ElementTriP1())
        interior = np.setdiff1d(np.arange(basis.N), basis.get_dofs().all())
        n = len(interior)
        if 20000 <= n <= 100000:
            best = (mesh, basis, interior, level)
            if n >= target:
                break
        if n > 100000:
            break
        mesh = mesh.refined()
    if best is None:
        raise ValueError(f'no acceptable 20k-100k uniform-refinement level; last n={n}, target={target}')
    mesh, basis, interior, level = best
    A = asm(laplace, basis).tocsr()[interior][:, interior].tocsr()
    b = np.asarray(asm(rhs, basis))[interior]
    A.sum_duplicates(); A.sort_indices()
    if A.nnz > 500000 or A.shape[0] < 20000 or A.shape[0] > 100000:
        raise ValueError(f'out of bounds n={A.shape[0]}, nnz={A.nnz}')
    if np.any(A.diagonal() <= 0) or not np.all(np.isfinite(A.data)):
        raise ValueError('non-SPD candidate')
    if sensitivity:
        # Nodal uniform load; assembly by mass matrix times nodal values.
        from skfem.models.poisson import mass
        load = np.random.default_rng(seed + 100000).uniform(size=basis.N)
        b = np.asarray(asm(mass, basis) @ load)[interior]
    return A, b, {'seed':seed, 'geometry':geometry, 'target_n':target,
                   'n':A.shape[0], 'nnz':A.nnz, 'refinements':level,
                   'load':'uniform_nodes' if sensitivity else 'constant_one'}

def sample_spec(split, index):
    sizes = {'train':750, 'val':15, 'test':300}
    bases = {'train':110000, 'val':210000, 'test':310000}
    assert 0 <= index < sizes[split]
    # even class counts in each split, nonoverlapping seed ranges.
    return bases[split]+index, index%3

if __name__ == '__main__':
    import argparse, json
    p=argparse.ArgumentParser(); p.add_argument('--split',choices=['train','val','test'],default='train'); p.add_argument('--index',type=int,default=0)
    args=p.parse_args(); seed, geometry=sample_spec(args.split,args.index)
    A,b,meta=make_sample(seed,geometry)
    print(json.dumps(meta)); print('b_norm',np.linalg.norm(b))
