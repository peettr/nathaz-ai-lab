"""Native LUW flags, physical ground at z=20, building STL crossings; offline only."""
from pathlib import Path
import sys,json,struct,time
import numpy as np
R=Path(__file__).resolve().parent; C0=R.parent/'phaseC0_links';C1=R.parent/'phaseC1_gate01'
sys.path[:0]=[str(C0),str(C1)]
from link_q import compute,DIRS
from ibm_geometry import read_case_e,clean_mesh
from analytic_links import NATIVE_D3Q19
start=time.monotonic();a=np.load(R/'step4_flags_z0_90.npz')['flags'];assert a.shape==(91,500,500)
tri,mesh=clean_mesh(read_case_e())
# The original native mask is preserved: subground fluid is excluded only at record selection.
records,meta=compute(tri,a==1)
cell=meta['cell'];di=meta['di'];q=meta['q'];hit=meta['hit'];owner=meta['owner'];counts=meta['counts']
source_z=cell//250000;dz=np.asarray(DIRS,dtype=np.int8)[di,2].astype(np.int32);target_z=source_z+dz
sel=source_z>=21; ground=sel&(target_z<=20);building=sel&(target_z>=21)&(hit>=0);unknown=sel&(target_z>=21)&(hit<0)
# Ground only includes actual native fluid-to-solid links; q=.5. Unknown is not a wall position.
end=building&((q<=.001)|(q>=.999));valid=building&~end&(q>0)&(q<1)
qout=np.full(int(sel.sum()),.5,dtype='<f4');ownerout=np.full(len(qout),3,dtype='u1')
si=np.flatnonzero(sel);g=ground[sel];b=valid[sel];e=end[sel];bw=building[sel]
ownerout[g]=2;ownerout[bw]=1;qout[b]=q[si[b]]
assert len(qout)==int(ground.sum()+building.sum()+unknown.sum()),(len(qout),int(ground.sum()+building.sum()+unknown.sum()))
assert np.isfinite(qout).all() and np.all((qout>0)&(qout<1))
native=np.empty(len(qout),dtype=[('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')])
native['cell']=cell[sel];native['direction']=np.array([NATIVE_D3Q19.index(v) for v in DIRS],dtype='u1')[di[sel]];native['q']=qout;native['owner']=ownerout
np.savez_compressed(R/'step4_native_links_sparse.npz',records=native)
# Existing prepare_ibb.csr rejects owner=3. Same documented binary layout, with audit owner 3 retained.
order=np.lexsort((native['direction'],native['cell']));ordered=native[order]
n=500*500*91;offsets=np.zeros(n+1,dtype='<u4');offsets[1:]=np.cumsum(np.bincount(ordered['cell'],minlength=n))
path=R/'step4_native_links.csr'
with path.open('xb') as f:
 f.write(struct.pack('<QQ',n,len(ordered)));f.write(offsets.tobytes());f.write(ordered['direction'].tobytes());f.write(ordered['q'].tobytes());f.write(ordered['owner'].tobytes())
assert path.stat().st_size==16+4*(n+1)+6*len(ordered)
# Fine-grained distribution and simple comparison to earlier 63-layer audit.
z_hist={k:np.bincount(source_z[m],minlength=91).astype(int).tolist() for k,m in [('building',building),('ground',ground),('unknown',unknown)]}
xy=cell[unknown]%250000
xy_hist=np.histogram2d(xy%500,xy//500,bins=(25,25),range=((0,500),(0,500)))[0].astype(int)
np.savez_compressed(R/'step4_unknown_xy.npz',hist=xy_hist)
old=np.load(R/'native_links_sparse.npz')['records'];oldkey=old['cell'].astype('u8')*19+old['direction'];newkey=native['cell'].astype('u8')*19+native['direction'];common=np.intersect1d(oldkey,newkey,assume_unique=True)
hist,edges=np.histogram(qout,bins=[0,.001,.01,.1,.25,.5,.75,.9,.99,.999,1])
stats={'source_flags':str(R/'step4_flags_z0_90.npz'),'shape':list(a.shape),'source_z_min':21,'target_ground_z_le':20,'links':len(native),'building':int(building.sum()),'ground':int(ground.sum()),'unknown':int(unknown.sum()),'endpoint_building_fallback':int(end.sum()),'building_valid_q':int(valid.sum()),'ground_halfway':int(ground.sum()),'subground_excluded':int((~sel).sum()),'q_hist_edges':edges.tolist(),'q_hist_counts':hist.tolist(),'q_lt_half':int((qout<.5).sum()),'q_ge_half':int((qout>=.5).sum()),'z_hist':z_hist,'unknown_xy_hist_25x25':xy_hist.tolist(),'unknown_xy_bounds':[[int((xy%500).min()),int((xy//500).min())],[int((xy%500).max()),int((xy//500).max())]] if len(xy) else None,'old_63layer_links':len(old),'common_old':len(common),'new_only':len(native)-len(common),'old_only':len(old)-len(common),'csr_bytes':path.stat().st_size,'npz_bytes':(R/'step4_native_links_sparse.npz').stat().st_size,'elapsed_s':time.monotonic()-start,'caveat':'z=0..90 only; owner=3 unknown must never be treated as resolved IBB; CSR includes owner 3 for audit, loader currently rejects owner>2; full-height flags absent'}
(R/'step4_native_stats.json').write_text(json.dumps(stats,indent=2)+'\n')
print(json.dumps({k:stats[k] for k in ('links','building','ground','unknown','endpoint_building_fallback','subground_excluded','common_old','csr_bytes','elapsed_s')},indent=2),flush=True)
