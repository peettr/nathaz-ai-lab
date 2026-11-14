"""Build new isolated Case E crop stages by deleting whole connected STL shells."""
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import shutil, hashlib, json, tarfile
R=Path(__file__).resolve().parent
OLD=R.parent/'resolution_crop/stage_C1'
DT=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')])
BOX=(0.,300.,80.,330.)
MARGIN=30.

def trim(src,dst):
    with open(src,'rb') as f:
        header=f.read(80); count=int.from_bytes(f.read(4),'little'); a=np.fromfile(f,dtype=DT)
    assert count==9210 and len(a)==count
    faces=a['v'][:-12]
    pts,inv=np.unique(faces.reshape(-1,3),axis=0,return_inverse=True)
    f=inv.reshape(-1,3); i=np.repeat(f[:,0],2); j=f[:,1:].reshape(-1)
    edges=coo_matrix((np.ones(len(i),dtype=bool),(i,j)),shape=(len(pts),len(pts)))
    n,lab=connected_components(edges,directed=False); group=lab[f[:,0]]
    assert np.all(lab[f]==group[:,None]); keep=np.ones(n,dtype=bool); records=[]
    for c in range(n):
        tri=faces[group==c]; low=tri.min(axis=(0,1));high=tri.max(axis=(0,1))
        # open side planes cannot intersect the kept geometry; keep a 30 m outlet strip
        discard=bool(high[0]>=BOX[1]-MARGIN or low[1]<=BOX[2]+MARGIN or high[1]>=BOX[3]-MARGIN or low[0]<=BOX[0])
        keep[c]=not discard
        if discard: records.append(dict(component=int(c),triangles=int(len(tri)),bbox_min=low.tolist(),bbox_max=high.tolist()))
    out=np.concatenate((a[:-12][keep[group]],a[-12:]))
    with open(dst,'wb') as f:
        f.write(header);f.write(len(out).to_bytes(4,'little'));out.tofile(f)
    assert (not np.any(out[:-12]['v'][:,:,0]>=BOX[1]-MARGIN))
    wall=np.array([[205.00008,205.60004],[226.00008,231.10004],[219.50008,227.10004],[230.50008,220.10004]])
    distances=[]
    for p in wall:
        distances.append(float(min(np.linalg.norm(np.maximum(np.maximum(np.array(x['bbox_min'][:2])-p,p-np.array(x['bbox_max'][:2])),0)) for x in records)))
    return dict(input_triangles=count,components=n,deleted_components=len(records),deleted_triangles=sum(x['triangles'] for x in records),retained_building_triangles=int(keep[group].sum()),wall_to_nearest_deleted_bbox_m=distances,deleted=records)

def stage(tag='C1v2',dx=1.):
    root=R/('stage_'+tag);assert not root.exists()
    shutil.copytree(OLD,root,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
    stl=root/'case/proj_temp/CaseE_PF.stl'
    stats=trim(OLD/'case/proj_temp/CaseE_PF.stl',stl)
    if dx!=1.:
        c=root/'case/conf.luwpf';s=c.read_text()
        for a,b in [('cell_size = 1.0','cell_size = 0.5'),('purge_avg = 20000','purge_avg = 40000'),('run_nstep = 31000','run_nstep = 62000'),('purge_avg_stride = 40','purge_avg_stride = 80')]:
            assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
        c.write_text(s)
    manifest={str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [root/'case/proj_temp/CaseE_PF.stl',root/'case/wind_bc/profile.dat',root/'case/conf.luwpf',root/'FluidX3D/src/setup.cpp']}
    (R/(tag+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    (R/(tag+'_geometry.json')).write_text(json.dumps(stats,indent=2)+'\n')
    with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as tar:
        tar.add(root/'FluidX3D',arcname='FluidX3D');tar.add(root/'case',arcname='case')
    print(tag,stats['deleted_components'],stats['retained_building_triangles'],stats['wall_to_nearest_deleted_bbox_m'],manifest,flush=True)
if __name__=='__main__':stage()
