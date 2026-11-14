"""Offline Case E IBM marker geometry; no solver or GPU dependency.

Usage: python3.10 ibm_geometry.py --h 1 --out .
Input PF triangles are cropped x-=760,y-=750, last 12 base triangles excluded.
Grid proxy matches R11: voxel (i,j,k) tests STL section at (i-1,j-1,k).
"""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np

STL = Path('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl')
R11 = Path('./24_Urban_Wind_LBM/04_Handoffs/from_22_Lab_20261015/06_Logs_luw')
TRI_DTYPE = np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')])

def read_case_e(path=STL):
    with open(path,'rb') as f:
        f.seek(80); count=int.from_bytes(f.read(4),'little'); data=np.fromfile(f,dtype=TRI_DTYPE)
    if count!=9210 or len(data)!=count: raise ValueError('Unexpected Case E PF STL triangle count')
    tri=data['v'][:-12].astype(np.float64)
    if not (np.all((tri[:,:,0]>760)&(tri[:,:,0]<1260)) and np.all((tri[:,:,1]>750)&(tri[:,:,1]<1250))):
        raise ValueError('12-base/crop contract changed')
    tri[:,:,0]-=760.;tri[:,:,1]-=750.
    return tri

def clean_mesh(tri, tol=1e-5):
    """Drop zero-area/duplicate faces; audit edge incidence and winding (do not silently repair)."""
    area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
    valid=np.isfinite(tri).all(axis=(1,2)) & (area>1e-10)
    tri=tri[valid]; keys=np.rint(tri/tol).astype(np.int64)
    canonical=np.sort(keys,axis=1).reshape(len(keys),9)
    _,idx=np.unique(canonical,axis=0,return_index=True); idx=np.sort(idx)
    duplicates=len(tri)-len(idx);tri=tri[idx];keys=keys[idx]
    verts,inv=np.unique(keys.reshape(-1,3),axis=0,return_inverse=True)
    ids=inv.reshape(-1,3)
    edges=np.concatenate([ids[:,[0,1]],ids[:,[1,2]],ids[:,[2,0]]])
    unordered=np.sort(edges,axis=1)
    unique,ei,counts=np.unique(unordered,axis=0,return_inverse=True,return_counts=True)
    signs=np.where(edges[:,0]<edges[:,1],1,-1)
    wind=np.bincount(ei,weights=signs,minlength=len(unique))
    info={'input_faces':int(len(valid)),'degenerate':int((~valid).sum()),'duplicates':int(duplicates),
          'retained_faces':int(len(tri)),'unique_vertices':int(len(verts)),
          'open_edges':int((counts==1).sum()),'nonmanifold_edges':int((counts>2).sum()),
          'inconsistent_two_face_edges':int(((counts==2)&(wind!=0)).sum()),
          'signed_volume_m3':float(np.einsum('ij,ij->',tri[:,0],np.cross(tri[:,1],tri[:,2]))/6),
          'area_m2':float(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1).sum()/2)}
    return tri,info

def markers_from_triangles(tri,h=1.,d_in=0.):
    """Triangular barycentric n-way split, all subedges <= h; one area-weighted centroid/subtriangle."""
    if h<=0 or d_in<0:raise ValueError('h>0, d_in>=0')
    points=[];normals=[];areas=[]
    for a,b,c in tri:
        nvec=np.cross(b-a,c-a);area=np.linalg.norm(nvec)/2
        if area<=0:continue
        normal=nvec/(2*area)
        count=max(1,int(math.ceil(max(np.linalg.norm(b-a),np.linalg.norm(c-b),np.linalg.norm(a-c))/h)))
        def vertex(i,j):return a+(i/count)*(b-a)+(j/count)*(c-a)
        subarea=area/(count*count)
        for i in range(count):
            for j in range(count-i):
                p=vertex(i,j);q=vertex(i+1,j);r=vertex(i,j+1)
                points.append((p+q+r)/3-d_in*normal);normals.append(normal);areas.append(subarea)
                if i+j<count-1:
                    s=vertex(i+1,j+1)
                    points.append((q+r+s)/3-d_in*normal);normals.append(normal);areas.append(subarea)
    return np.asarray(points,dtype=np.float64).reshape(-1,3),np.asarray(normals,dtype=np.float64).reshape(-1,3),np.asarray(areas,dtype=np.float64)

def phi(r):
    r=np.abs(np.asarray(r,dtype=float));result=np.zeros_like(r)
    a=r<=.5; b=(r>.5)&(r<1.5)
    result[a]=(1+np.sqrt(np.maximum(0,1-3*r[a]**2)))/3
    result[b]=(5-3*r[b]-np.sqrt(np.maximum(0,1-3*(1-r[b])**2)))/6
    return result

def support(x):
    """Three nearest grid centers per axis, physical centers at integer positions."""
    x=np.asarray(x,dtype=float);center=np.floor(x+.5).astype(int)
    axes=center[:,None]+np.array([-1,0,1])[None,:]
    grid=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,3)
    w=np.prod(phi(grid-x),axis=1)
    return grid,w

def section_segments(tri,z):
    a=tri[:,:,2]; hit=((a<=z)&(z<np.roll(a,-1,axis=1)))|((np.roll(a,-1,axis=1)<=z)&(z<a))
    sel=hit.sum(axis=1)==2
    t=tri[sel]; hit=hit[sel]
    if not len(t):return np.empty((0,2,2))
    ends=np.roll(t,-1,axis=1)
    w=(z-t[:,:,2])/np.where(ends[:,:,2]!=t[:,:,2],ends[:,:,2]-t[:,:,2],1)
    xy=(t+w[:,:,None]*(ends-t))[:,:,:2]
    seg=xy[hit].reshape(-1,2,2)
    key=np.sort(np.rint(seg*1e4).astype(np.int64),axis=1).reshape(-1,4)
    _,ids=np.unique(key,axis=0,return_index=True)
    return seg[np.sort(ids)]

def voxel_proxy(tri,nx=500,ny=500,nz=62):
    """R11 half-open z sections + horizontal ray parity; (i-1,j-1,k) mesh coordinates.
    This is NOT the 3-D OpenCL voxelize_mesh flag buffer; parity odd rows audited.
    """
    solid=np.zeros((nz,ny,nx),dtype=bool);odd=0
    xs=np.arange(nx)-1.; ys=np.arange(ny)-1.
    for k in range(nz):
        seg=section_segments(tri,float(k))
        if not len(seg):continue
        low=seg[:,0];high=seg[:,1]
        for j,y in enumerate(ys):
            crossing=(low[:,1]<=y)&(y<high[:,1]) | (high[:,1]<=y)&(y<low[:,1])
            if not crossing.any():continue
            lo=low[crossing];hi=high[crossing]
            hits=np.sort(lo[:,0]+(hi[:,0]-lo[:,0])*(y-lo[:,1])/(hi[:,1]-lo[:,1]))
            if len(hits)%2:odd+=1;continue
            solid[k,j]=np.searchsorted(hits,xs,side='left')%2==1
    return solid,odd

def support_audit(markers,areas,solid):
    """Chunked nonzero 3-point support; thin-lane counts are a voxel proxy, not parcel attribution."""
    nz,ny,nx=solid.shape
    shell=np.zeros_like(solid);counts=np.zeros(28,dtype=np.int64);invalid=0;ground=0
    invalid_area=ground_area=0.; narrow_markers=0;narrow_area=0.
    # A fluid voxel between solid cells in x or y with both walls <=2 grid steps away.
    # This includes cavities/concave single buildings; it cannot identify parcel ownership.
    narrow=np.zeros_like(solid)
    for axis in (1,2):
        plus=np.zeros_like(solid);minus=np.zeros_like(solid)
        for d in (1,2):
            sl=[slice(None)]*3;dst=[slice(None)]*3
            sl[axis]=slice(d,None);dst[axis]=slice(None,-d)
            minus[tuple(sl)] |= solid[tuple(dst)]
            plus[tuple(dst)] |= solid[tuple(sl)]
        narrow |= minus & plus & ~solid
    for lo in range(0,len(markers),20000):
        p=markers[lo:lo+20000];a=areas[lo:lo+len(p)]
        center=np.floor(p+.5).astype(np.int32)
        c=np.zeros(len(p),dtype=np.uint8);bad=np.zeros(len(p),dtype=bool);floor=np.zeros(len(p),dtype=bool);tight=np.zeros(len(p),dtype=bool)
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    x=center[:,0]+dx;y=center[:,1]+dy;z=center[:,2]+dz
                    active=(phi(x-p[:,0])*phi(y-p[:,1])*phi(z-p[:,2]))>1e-14
                    inside=(x>=0)&(x<nx)&(y>=0)&(y<ny)&(z>=0)&(z<nz)
                    bad|=active & ~inside;floor|=active & (z<=0)
                    ids=np.flatnonzero(active & inside)
                    occupied=solid[z[ids],y[ids],x[ids]]
                    c[ids]+=occupied.astype(np.uint8)
                    tight[ids]|=narrow[z[ids],y[ids],x[ids]]
                    chosen=ids[occupied];shell[z[chosen],y[chosen],x[chosen]]=True
        counts+=np.bincount(c,minlength=28);invalid+=int(bad.sum());ground+=int(floor.sum())
        invalid_area+=float(a[bad].sum());ground_area+=float(a[floor].sum())
        narrow_markers+=int(tight.sum());narrow_area+=float(a[tight].sum())
    return {'solid_support_histogram_0_to_27':counts.tolist(),'markers_with_any_solid_support':int(len(markers)-counts[0]),
            'markers_incomplete_domain_support':invalid,'incomplete_domain_area_m2':invalid_area,
            'markers_support_intersects_ground_z_le_0':ground,'ground_overlap_area_m2':ground_area,
            'unique_solid_voxels_to_relabel_fluid_for_shell':int(shell.sum()),
            'solid_voxels_total_proxy':int(solid.sum()),'fraction_solid_to_relabel':float(shell.sum()/max(1,solid.sum())),
            'narrow_fluid_cells_opposite_solids_within_2_each_axis':int(narrow.sum()),
            'markers_support_touching_narrow_cells':narrow_markers,'narrow_contact_marker_area_m2':narrow_area}

def point_audit(markers,solid):
    points={int(r['id']):r for r in csv.DictReader((R11/'CaseE_W_points_full_r7.csv').open())}
    from scipy.spatial import cKDTree
    tree=cKDTree(markers)
    rows=[]
    for idx in (50,51,52,54):
        p=points[idx]; xyz=np.array([float(p['x'])+1010.50008-760,float(p['y'])+1000.60004-750,2.])
        # R11 sample is at physical xy shifted +1, z=2; 3-point interpolation support here is a proxy.
        sample=xyz+np.array([1.,1.,0.]); dist,index=tree.query(xyz)
        lattice,w=support(sample); nz,ny,nx=solid.shape
        marker_support,_=support(markers[index]);overlap=set(map(tuple,lattice))&set(map(tuple,marker_support))
        rows.append({'id':idx,'point_to_nearest_marker_m':float(dist),'nearest_marker_xyz_m':markers[index].tolist(),
                     'sample_xyz_m':sample.tolist(),'sample_support_overlap_nearest_marker_cells':len(overlap),
                     'sample_support_overlap_nearest_marker_weight':float(sum(w[i] for i,node in enumerate(lattice) if tuple(node) in overlap)),
                     'sample_support_solid_cells':int(sum(solid[z,y,x] for x,y,z in lattice if 0<=x<nx and 0<=y<ny and 0<=z<nz)),
                     'nearest_marker_distance_to_shifted_sample_m':float(np.linalg.norm(markers[index]-sample))})
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--h',type=float,default=1.);ap.add_argument('--d-in',type=float,default=0.);ap.add_argument('--delta-s',type=float,default=1.)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent);args=ap.parse_args()
    if args.delta_s<=0:raise ValueError('delta_s>0')
    args.out.mkdir(parents=True,exist_ok=True)
    tri,stats=clean_mesh(read_case_e());markers,normals,areas=markers_from_triangles(tri,args.h,args.d_in)
    area_error=abs(areas.sum()-stats['area_m2'])/stats['area_m2'];assert area_error<1e-6
    outfile=args.out/('CaseE_markers_h'+str(args.h).replace('.','p')+'.npz')
    np.savez_compressed(outfile, X=markers.astype('<f4'),n=normals.astype('<f4'),A=areas.astype('<f8'))
    if outfile.stat().st_size>=50_000_000:raise ValueError('single output >50 MB; choose coarser h or chunk')
    solid,odd=voxel_proxy(tri)
    summary={'source':str(STL),'transform':'remove final 12 base triangles; x-=760, y-=750, z unchanged; no rotation in PF frame',
             'grid_proxy':'R11 z-section parity with voxel center(i-1,j-1,k), not GPU TYPE_S actual flags',
             'h_m':args.h,'d_in_m_assumption':args.d_in,'delta_s_m_assumption':args.delta_s,'cleaning':stats,
             'markers':int(len(markers)),'sum_area_m2':float(areas.sum()),'relative_area_error':float(area_error),
             'proxy_odd_crossing_rows':odd,'support':support_audit(markers,areas,solid),
             'wall_points':point_audit(markers,solid),'npz':str(outfile),'npz_bytes':outfile.stat().st_size}
    (args.out/'phase0_stats.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print(json.dumps({'markers':summary['markers'],'area_error':area_error,'cleaning':stats,'support':summary['support'],'odd_rows':odd,'npz_bytes':outfile.stat().st_size},ensure_ascii=False))
if __name__=='__main__':main()
