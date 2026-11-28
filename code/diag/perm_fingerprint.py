"""第⑥-映射核验补：空间平滑指纹检验（判读写定 11-20 21:48）。"""
import gzip,io,json,numpy as np,os
from scipy.spatial import cKDTree
from scipy.stats import pearsonr
H=os.path.dirname(os.path.abspath(__file__)); B=H+'/..'
def npy(p): return np.load(io.BytesIO(gzip.open(p).read()))
out={}
rng=np.random.default_rng(0)
for g,gf in (('medium','medium_gradient.npy.gz'),('fine','fine_gradient_final.npy.gz')):
    grad=npy(H+'/'+gf).ravel(); C=npy(f'{B}/geom/returned/{g}_centres.npy.gz'); perm=npy(f'{B}/perm/returned/output/{g}/{g}_perm.npy.gz').ravel()
    n=len(grad); assert len(perm)==n==len(C)
    t=cKDTree(C); _,nb=t.query(C,k=2); nb=nb[:,1]
    def r_of(gs):  # gs: gradient in serial order
        x=np.log10(np.abs(gs)+1e-30); return float(pearsonr(x,x[nb])[0])
    g_serial=np.empty(n); g_serial[perm]=grad          # serial_index = perm[global_index]
    r_perm=r_of(g_serial); r_id=r_of(grad); r_rand=r_of(grad[rng.permutation(n)])
    ok=(r_perm>=0.8) and (r_perm-r_id>=0.3) and (r_perm-r_rand>=0.5)
    out[g]=dict(r_perm=r_perm,r_id=r_id,r_rand=r_rand,mapping_ok=bool(ok))
json.dump(out,open(H+'/perm_fingerprint.json','w'),indent=1); print(json.dumps(out,indent=1))
