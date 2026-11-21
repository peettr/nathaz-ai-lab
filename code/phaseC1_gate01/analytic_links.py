"""Analytic, sparse fluid-to-solid D3Q19 links for phase C1 audit.

Offline small geometry only. No fluid solve and no wall operator is implied.
Coordinates are cell centres at integer (x,y,z), lattice Δx=1. A link
starts at fluid centre and ends at neighbouring solid centre. Uses a plane
or a cylinder extruded along periodic z. Nonperiodic x/y outer faces are
excluded from the q list (they need a separate inlet/outlet/wall policy).
"""
import argparse
import json
from pathlib import Path
import numpy as np

# Verified against core/cfd_core/FluidX3D/src/kernel.cpp:890-893, 949-958.
NATIVE_D3Q19 = ((0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),
 (0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),
 (0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),
 (0,1,-1),(0,-1,1))
DT = np.dtype([('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')], align=False)

def cylinder_q(p, v, cx, cy, radius):
    """First intersection of p+q*v with exact infinite cylinder, q in (0,1)."""
    p=np.asarray(p,dtype=np.float64);v=np.asarray(v,dtype=np.float64)
    x,y=p[0]-cx,p[1]-cy
    a=v[0]**2+v[1]**2
    if not a:return None
    b=2*(x*v[0]+y*v[1]);c=x*x+y*y-radius*radius
    disc=b*b-4*a*c
    if disc<0:return None
    roots=((-b-np.sqrt(disc))/(2*a),(-b+np.sqrt(disc))/(2*a))
    return next((float(r) for r in roots if 1e-9<r<1-1e-9),None)

def plane_q(p, v, axis, location):
    if not v[axis]:return None
    q=(location-p[axis])/v[axis]
    return float(q) if 1e-9<q<1-1e-9 else None

def generate(shape, geometry, *, centre=(10.,10.), radius=3.3,
             plane_axis=1, plane_at=4.25):
    """Return sorted sparse q and diagnostics; no periodic-wrap q links."""
    nx,ny,nz=shape
    assert all(3<=n for n in shape) and np.prod(shape)<2**32
    def solid(x,y,z):
        if geometry=='cylinder':return (x-centre[0])**2+(y-centre[1])**2 < radius**2
        return (x,y,z)[plane_axis]>=plane_at
    rows=[];skipped=0;no_hit=0
    for z in range(nz):
      for y in range(ny):
       for x in range(nx):
        if solid(x,y,z):continue
        n=x+nx*(y+ny*z)
        for i,(dx,dy,dz) in enumerate(NATIVE_D3Q19[1:],1):
            xx,yy,zz=x+dx,y+dy,z+dz
            if not(0<=xx<nx and 0<=yy<ny):continue
            zz%=nz
            if not solid(xx,yy,zz):continue
            v=(dx,dy,dz)
            q=(cylinder_q((x,y,z),v,*centre,radius) if geometry=='cylinder'
               else plane_q((x,y,z),v,plane_axis,plane_at))
            if q is None:
                no_hit+=1;continue
            back1=(x-dx,y-dy,(z-dz)%nz)
            back2=(x-2*dx,y-2*dy,(z-2*dz)%nz)
            def usable(p):return (0<=p[0]<nx and 0<=p[1]<ny and not solid(*p))
            if not usable(back1) or (q<.5 and not usable(back2)):
                skipped+=1;continue
            rows.append((n,i,q,1))
    arr=np.array(rows,dtype=DT)
    if len(arr):arr.sort(order=('cell','direction'))
    return arr,{'geometry':geometry,'shape':shape,'active_links':len(arr),
                'fallback_missing_fluid_neighbor':skipped,'intersection_unresolved':no_hit,
                'q_lt_half':int(np.count_nonzero(arr['q']<.5)),
                'q_ge_half':int(np.count_nonzero(arr['q']>=.5))}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--kind',required=True,choices=('cylinder','plane'))
    ap.add_argument('--nx',type=int,default=44);ap.add_argument('--ny',type=int,default=12)
    ap.add_argument('--nz',type=int,default=3)
    ap.add_argument('--cx',type=float,default=11.);ap.add_argument('--cy',type=float,default=6.)
    ap.add_argument('--radius',type=float,default=2.25)
    ap.add_argument('--plane-at',type=float,default=4.25)
    args=ap.parse_args()
    if args.out.exists():raise SystemExit('refuse overwrite: '+str(args.out))
    records,stats=generate((args.nx,args.ny,args.nz),args.kind,
                            centre=(args.cx,args.cy),radius=args.radius,plane_at=args.plane_at)
    np.savez_compressed(args.out,records=records,stats_json=json.dumps(stats))
    print(json.dumps(stats))
if __name__=='__main__':main()
