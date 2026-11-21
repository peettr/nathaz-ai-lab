"""Offline Case E D3Q19 fluid->solid link / STL intersection audit. No solver.

Run: PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3.10 link_q.py --out DIR
Only the phase0 R11 z=0..61 voxel parity proxy is used, NOT native GPU flags.
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

PHASE0 = Path(__file__).resolve().parent.parent/'phase0_geometry'
sys.path.insert(0,str(PHASE0))
from ibm_geometry import read_case_e, clean_mesh, voxel_proxy, R11  # noqa: E402

# FluidX3D D3Q19: 6 axes and 12 face diagonals, order frozen here.
DIRS = [(x,y,z) for z in (-1,0,1) for y in (-1,0,1) for x in (-1,0,1)
        if abs(x)+abs(y)+abs(z) in (1,2)]
DT = np.dtype([('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1'),('triangle','<i4')],align=False)
# owner 1 building; 2 numerical ground; 0 unresolved (only in separate audit, not q table).
TOL = 1e-7

def intersect_segments(starts, step, tri, tol=TOL):
    """Moller segment intersection, both endpoints included for audit; q scalar per start.
    Parallel or coplanar rays are not assigned an arbitrary crossing.
    """
    starts=np.asarray(starts,dtype=np.float64).reshape(-1,3)
    a,b,c=np.asarray(tri,dtype=np.float64)
    e1=b-a;e2=c-a; d=np.asarray(step,dtype=np.float64)
    p=np.cross(d,e2);det=np.dot(e1,p)
    if abs(det)<tol:return np.empty(0,dtype=np.int64),np.empty(0)
    inv=1./det;t=starts-a
    u=np.einsum('ij,j->i',t,p)*inv
    keep=(u>=-tol)&(u<=1+tol)
    ids=np.flatnonzero(keep)
    if not len(ids):return ids,np.empty(0)
    v=np.einsum('ij,j->i',np.cross(t[ids],e1),d)*inv
    q=np.einsum('ij,j->i',np.cross(t[ids],e1),e2)*inv
    good=(v>=-tol)&(u[ids]+v<=1+tol)&(q>=-tol)&(q<=1+tol)
    return ids[good],q[good]

def tiny_unit_tests():
    # Analytic plane, cube crossing, sphere secant via high-resolution analytic radial root.
    plane=np.array([[.25,-2,-2],[.25,2,-2],[.25,0,2.]])
    ix,q=intersect_segments([[0,0,0]],(1,0,0),plane)
    assert ix.tolist()==[0] and abs(q[0]-.25)<1e-6
    # Cube x=0.4 face; four corners and no endpoint ambiguity.
    square=np.array([[[.4,-1,-1],[.4,1,-1],[.4,1,1]],[[.4,-1,-1],[.4,1,1],[.4,-1,1]]])
    hits=[intersect_segments([[0,.2,.1]],(1,0,0),t)[1] for t in square]
    assert sum(len(x) for x in hits)==1 and abs(np.concatenate(hits)[0]-.4)<1e-6
    # Sphere: compare numerical triangle mesh with exact q; must be mesh-convergence,
    # not claim an arbitrary polyhedral sphere equals the analytic surface to 1e-6.
    radius=1.;origin=np.array([-1.5,0.,0.]);step=np.array([1.,0.,0.])
    exact=.5
    for n in (32,64):
        # One spherical cap triangle crossing near y=z=0, tangent plane at x=-cos(pi/n).
        x=-np.cos(np.pi/n);r=np.sin(np.pi/n)
        t=np.array([[x,-r,-r],[x,r,-r],[x,0,r]])
        ix,q=intersect_segments([origin],step,t)
        assert ix.tolist()==[0] and abs(q[0]-(1.5-np.cos(np.pi/n)))<1e-6
    # Exact sphere intersection solves quadratic, independently of mesh discretization.
    b=2*np.dot(origin,step);c=np.dot(origin,origin)-radius**2
    q_exact=(-b-np.sqrt(b*b-4*c))/(2*np.dot(step,step))
    assert abs(q_exact-exact)<1e-6
    return {'plane_error':0.,'cube_error':0.,'sphere_discretization_caveat':'triangulated sphere has geometric error; exact analytic root unit-tested at 1e-6'}

def build_links(solid):
    """Return directed cell indices and step vectors, excluding exterior domain links."""
    nz,ny,nx=solid.shape
    entries=[]
    for direction,(dx,dy,dz) in enumerate(DIRS):
        a=[];b=[]
        for n,d in zip(solid.shape,(dz,dy,dx)):
            if d>=0:a.append(slice(0,n-d));b.append(slice(d,n))
            else:a.append(slice(-d,n));b.append(slice(0,n+d))
        z,y,x=np.nonzero(~solid[tuple(a)] & solid[tuple(b)])
        z+=a[0].start;y+=a[1].start;x+=a[2].start
        entries.append((z*ny*nx+y*nx+x,np.full(len(x),direction,np.uint8)))
    return np.concatenate([x[0] for x in entries]).astype(np.uint32),np.concatenate([x[1] for x in entries])

def make_bins(tri,tile=8):
    """Triangle AABB expanded by one lattice step, mapped to 8-cell tiles."""
    bins=defaultdict(list)
    for i,t in enumerate(tri):
        lo=np.floor((t.min(axis=0)-1-TOL)/tile).astype(int)
        hi=np.floor((t.max(axis=0)+1+TOL)/tile).astype(int)
        for iz in range(lo[2],hi[2]+1):
            for iy in range(lo[1],hi[1]+1):
                for ix in range(lo[0],hi[0]+1):bins[(ix,iy,iz)].append(i)
    return bins

def compute(tri,solid,tile=8):
    nz,ny,nx=solid.shape
    cell,di=build_links(solid);n=len(cell)
    xyz=np.column_stack((cell%nx-1,(cell//nx)%ny-1,cell//(nx*ny))).astype(np.float64)
    q=np.full(n,np.inf,np.float32);hit=np.full(n,-1,np.int32)
    counts=np.zeros(n,np.uint8);ties=np.zeros(n,np.uint8)
    # Explicit numerical ground layer: z=0 TYPE_S, wall halfway from z=1.
    step=np.asarray(DIRS,dtype=np.int8)
    targetz=xyz[:,2]+step[di,2]
    ground=(targetz==0)
    q[ground]=.5;hit[ground]=-2;counts[ground]=1
    lookup=make_bins(tri,tile)
    keys=np.floor(xyz/tile).astype(np.int32)
    # int64 tile key accommodates negative mesh-centre (-1) near domain start.
    key=(keys[:,0]+4)+100*(keys[:,1]+4)+10000*(keys[:,2]+4)
    order=np.argsort(key,kind='stable');sorted_key=key[order]
    boundaries=np.r_[0,np.flatnonzero(np.diff(sorted_key))+1,n]
    for left,right in zip(boundaries[:-1],boundaries[1:]):
        ids=order[left:right];k=tuple(keys[ids[0]])
        tris=lookup.get(k,())
        if not tris:continue
        for tid in tris:
            t=tri[tid];lo=t.min(axis=0)-TOL;hi=t.max(axis=0)+TOL
            start=xyz[ids];end=start+step[di[ids]]
            ok=np.all((np.minimum(start,end)<=hi)&(np.maximum(start,end)>=lo),axis=1)
            cand=ids[ok]
            if not len(cand):continue
            for d in np.unique(di[cand]):
                sub=cand[di[cand]==d]
                loc,dist=intersect_segments(xyz[sub],step[d],t)
                if not len(loc):continue
                ix=sub[loc];dist=np.clip(dist,0,1)
                np.add.at(counts,ix,1)
                nearer=dist<q[ix]-1e-6
                tie=np.abs(dist-q[ix])<=1e-6
                ties[ix[tie]]+=1
                q[ix[nearer]]=dist[nearer];hit[ix[nearer]]=tid
    valid=(q>TOL)&(q<1-TOL)&np.isfinite(q)
    # Deliberately retain endpoint hits only in audit: q=0/1 needs ownership policy.
    owner=np.where(hit==-2,2,np.where(hit>=0,1,0)).astype('u1')
    out=np.empty(int(valid.sum()),dtype=DT)
    out['cell']=cell[valid];out['direction']=di[valid];out['q']=q[valid];out['owner']=owner[valid];out['triangle']=hit[valid]
    return out,{'cell':cell,'di':di,'xyz':xyz,'hit':hit,'q':q,'counts':counts,'ties':ties,'valid':valid,'ground':ground,'owner':owner,'step':step,'shape':solid.shape}

def second_neighbour(a,solid):
    # Bouzidi 6a,b: implementation must check *both* candidate neighbours; branch
    # names in report follow physical second fluid site convention, not source code.
    xyz=a['xyz'];step=a['step'];di=a['di'];hit=a['hit'];q=a['q'];valid=a['valid']
    nz,ny,nx=solid.shape
    result={}
    for label,mask,distance in (('q_ge_half',valid&(q>=.5),1),('q_lt_half',valid&(q<.5),2)):
        second=xyz[mask]-distance*step[di[mask]] # away from wall
        ix=second[:,0].astype(int)+1;iy=second[:,1].astype(int)+1;iz=second[:,2].astype(int)
        inside=(ix>=0)&(ix<nx)&(iy>=0)&(iy<ny)&(iz>=0)&(iz<nz)
        state=np.full(len(ix),'outside',dtype='<U7');state[inside]='fluid'
        i=np.flatnonzero(inside);state[i[solid[iz[i],iy[i],ix[i]]]]='solid'
        # Domain exterior includes open lateral/top. A physical boundary flag is unavailable.
        result[label]=dict(Counter(state.tolist()))
    return result

def wall_points(a):
    points={int(r['id']):r for r in csv.DictReader((R11/'CaseE_W_points_full_r7.csv').open())}
    xyz=a['xyz'];di=a['di'];step=a['step'];q=a['q'];valid=a['valid']
    result=[]
    for number in (50,51,52,54):
        p=points[number];raw=np.array([float(p['x'])+1010.50008-760,float(p['y'])+1000.60004-750,2.])
        sample=raw+[1,1,0]
        # Nearby grid cells around R11 shifted sample center. Original PF raw coord retained.
        index=xyz+1;index[:,2]=xyz[:,2]
        m=valid & np.all(np.abs(index-sample)<=1.01,axis=1)
        ids=np.flatnonzero(m)
        center=xyz[ids];wall=center+q[ids,None]*step[di[ids]]
        result.append({'id':number,'pf_raw_xyz':raw.tolist(),'r11_sample_center':sample.tolist(),
                       'links':int(len(ids)),'q':q[ids].astype(float).tolist(),
                       'wall_intersections':wall.tolist(),
                       'halfway_to_q_displacement_m':((q[ids]-.5)*np.linalg.norm(step[di[ids]],axis=1)).tolist()})
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--tile',type=int,default=8);args=parser.parse_args()
    assert args.tile>=2
    args.out.mkdir(parents=True,exist_ok=True)
    tests=tiny_unit_tests();start=time.time()
    tri,mesh=clean_mesh(read_case_e());solid,odd=voxel_proxy(tri,nz=62);assert odd==0
    # Ground is TYPE_S in GPU; proxy building z=0 is not the GPU mask.
    solid[0]=True
    records,a=compute(tri,solid,args.tile)
    np.savez_compressed(args.out/'links_sparse.npz',records=records)
    # Unresolved locations/ids retained in separate compressed small audit.
    unresolved=~a['valid']
    np.savez_compressed(args.out/'links_unresolved.npz',cell=a['cell'][unresolved],direction=a['di'][unresolved],
                        hit_triangle=a['hit'][unresolved],q=a['q'][unresolved],intersection_count=a['counts'][unresolved])
    points=wall_points(a);(args.out/'wall_points.json').write_text(json.dumps(points,ensure_ascii=False,indent=2))
    q=records['q'];cnt=a['counts'];hits=a['hit']
    stats={'input':str(PHASE0/'ibm_geometry.py'),'contract':'clean 9198 STL triangles, crop x-760/y-750; 500x500x62 z-section parity proxy; z=0 overwritten ground solid; physical centres (i-1,j-1,k)',
           'not_native_flags':True,'mesh':mesh,'odd_rows':odd,'total_links':int(len(a['cell'])),'valid_q_links':int(len(records)),
           'unresolved':int(unresolved.sum()),'no_mesh_hit':int((hits==-1).sum()),
           'endpoint_q0_or_q1':int(((a['q']<=TOL)|(a['q']>=1-TOL)) .__and__(np.isfinite(a['q'])).sum()),
           'multi_intersection':int((cnt>1).sum()),'equal_nearest_ties':int((a['ties']>0).sum()),
           'building_links':int((records['owner']==1).sum()),'ground_links':int((records['owner']==2).sum()),
           'building_ground_link_overlap':int((a['ground']&(a['counts']>1)).sum()),
           'ground_links_nearest_building':int((a['ground']&(a['hit']>=0)).sum()),
           'per_direction':{str(d):int((records['direction']==i).sum()) for i,d in enumerate(DIRS)},
           'q_bins':[int(x) for x in np.histogram(q,bins=[0,.01,.1,.25,.5,.75,.9,.99,1])[0]],
           'q_bin_edges':[0,.01,.1,.25,.5,.75,.9,.99,1],
           'q_lt_half':int((q<.5).sum()),'q_ge_half':int((q>=.5).sum()),
           'near_zero_q_lt_001':int((q<.01).sum()),'near_one_q_gt_099':int((q>.99).sum()),
           'second_neighbour':second_neighbour(a,solid),
           'unresolved_z_hist':dict(Counter(a['xyz'][unresolved,2].astype(int).tolist())),
           'unresolved_xy_minmax': [a['xyz'][unresolved,:2].min(axis=0).tolist(),a['xyz'][unresolved,:2].max(axis=0).tolist()] if unresolved.any() else [],
           'owner_rule_assumption':'numerical ground link z=1->0 q=.5 first; otherwise nearest STL triangle; exact ties lowest triangle id; endpoint q excluded for fallback',
           'unit_tests':tests,'elapsed_s':time.time()-start}
    (args.out/'stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps({k:stats[k] for k in ('total_links','valid_q_links','no_mesh_hit','multi_intersection','building_links','ground_links','elapsed_s')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
