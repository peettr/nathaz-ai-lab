"""Native Case E flags -> STL q audit and conservative LUW CSR (offline)."""
import sys, json, time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
C0=HERE.parent/'phaseC0_links'; C1=HERE.parent/'phaseC1_gate01'
sys.path[:0]=[str(C0),str(C1)]
from link_q import compute, DIRS
from ibm_geometry import read_case_e, clean_mesh
from analytic_links import NATIVE_D3Q19
from prepare_ibb import csr
FLAGS=HERE.parent.parent/'wp1_nearwall/city_stab/ma010_flags_z0_62.npz'
PROXY=C0/'run2/links_sparse.npz'
def main():
 t=time.monotonic(); a=np.load(FLAGS)['flags']; assert a.shape==(63,500,500)
 tri,mesh=clean_mesh(read_case_e())
 records,meta=compute(tri,a==1)
 cell=meta['cell']; di=meta['di']; q=meta['q']; owner=meta['owner']; hits=meta['hit']; finite=np.isfinite(q)
 # Native TYPE_S link with no reliable interior mesh crossing falls back to halfway.
 endpoint=finite & ((q<=1e-3)|(q>=1-1e-3))
 nohit=~finite
 fallback=endpoint|nohit
 q[fallback]=.5
 owner[nohit]=0
 # Any link aimed into z=0 ground is owner=2; explicit ground rule remains q=.5.
 ground=meta['ground'];owner[ground]=2;q[ground]=.5
 native=np.empty(len(cell),dtype=[('cell','<u4'),('direction','u1'),('q','<f4'),('owner','u1')])
 native['cell']=cell;native['direction']=np.array([NATIVE_D3Q19.index(v) for v in DIRS],dtype='u1')[di]
 native['q']=q;native['owner']=owner
 assert np.isfinite(q).all() and ((q>0)&(q<1)).all()
 np.savez_compressed(HERE/'native_links_sparse.npz',records=native)
 csr(native,(500,500,63),HERE/'native_links.csr')
 proxy=np.load(PROXY)['records']
 key=lambda x:x['cell'].astype('u8')*19+x['direction'].astype('u8')
 # Proxy direction indices map to native; proxy uses 62 layers.
 pk=proxy['cell'].astype('u8')*19+np.array([NATIVE_D3Q19.index(v) for v in DIRS],dtype='u1')[proxy['direction']]
 nk=key(native); common=np.intersect1d(nk,pk,assume_unique=True)
 hist,edges=np.histogram(q,bins=[0,.001,.01,.1,.25,.5,.75,.9,.99,.999,1.])
 stats={'flag_path':str(FLAGS),'shape':list(a.shape),'links':int(len(cell)),'building_owner':int((owner==1).sum()),'ground_owner':int((owner==2).sum()),'unresolved_owner':int((owner==0).sum()),'endpoint_fallback':int(endpoint.sum()),'no_hit_fallback':int(nohit.sum()),'ground_halfway':int(ground.sum()),'q_lt_half':int((q<.5).sum()),'q_ge_half':int((q>=.5).sum()),'hist_edges':edges.tolist(),'hist_counts':hist.tolist(),'proxy_valid_links':int(len(proxy)),'common_proxy_valid':int(len(common)),'native_only':int(len(nk)-len(common)),'proxy_only':int(len(pk)-len(common)),'csr_bytes':(HERE/'native_links.csr').stat().st_size,'npz_bytes':(HERE/'native_links_sparse.npz').stat().st_size,'elapsed_s':time.monotonic()-t,'rule':'endpoint [0,.001] or [.999,1] -> q=.5, owner retains building/ground; no mesh crossing -> q=.5 owner=0 pending review; z=0 ground q=.5 owner=2','caveat':'z=0..62 native flags only; cannot cover higher domain; not a production-ready full-height table'}
 (HERE/'native_stats.json').write_text(json.dumps(stats,indent=2))
 print(json.dumps(stats,indent=2),flush=True)
if __name__=='__main__':main()
