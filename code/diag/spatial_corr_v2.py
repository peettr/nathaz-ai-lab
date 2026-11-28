"""v2：梯度先按分区映射 perm 转到串行序（第⑥-映射核验补通过）。L26.21 第⑥-补：中/细档梯度密度在建筑周围盒内的空间相关（判读写定于卡第⑥-补 11-20 15:53）。
用法：python3 spatial_corr.py <geom目录>  （内含 medium_centres.npy.gz、medium_volumes.npy.gz、fine_centres.npy.gz、fine_volumes.npy.gz）"""
import sys, gzip, io, json, numpy as np, os
from scipy.spatial import cKDTree
from scipy.stats import pearsonr, spearmanr
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('./Windows/Fonts/NotoSansSC-VF.ttf'); plt.rcParams['font.family']='Noto Sans SC'; plt.rcParams['axes.unicode_minus']=False
H=os.path.dirname(os.path.abspath(__file__)); G=sys.argv[1]
def npy(p): return np.load(io.BytesIO(gzip.open(p).read()))
B=H+'/..'
def toserial(g,name):
    p=npy(f'{B}/perm/returned/output/{name}/{name}_perm.npy.gz').ravel(); s=np.empty_like(g); s[p]=g; return s
grad={'中':toserial(npy(H+'/medium_gradient.npy.gz').ravel(),'medium'),'细':toserial(npy(H+'/fine_gradient_final.npy.gz').ravel(),'fine')}
geo={'中':(npy(G+'/medium_centres.npy.gz'),npy(G+'/medium_volumes.npy.gz').ravel()),'细':(npy(G+'/fine_centres.npy.gz'),npy(G+'/fine_volumes.npy.gz').ravel())}
for g in grad: assert len(grad[g])==len(geo[g][1])==len(geo[g][0]), g
d=0.5; xs=np.arange(-16+d/2,16,d); zs=np.arange(d/2,16,d)
X,Y,Z=np.meshgrid(xs,xs,zs,indexing='ij'); P=np.c_[X.ravel(),Y.ravel(),Z.ravel()]
inside=(np.abs(P[:,0])<8)&(np.abs(P[:,1])<8)&(P[:,2]<8); P=P[~inside]
rho={}; cover={}; boxes={}
for g,(C,V) in geo.items():
    t=cKDTree(C); dist,idx=t.query(P); rho[g]=(grad[g]/V)[idx]
    inb=(np.abs(C[:,0])<=16)&(np.abs(C[:,1])<=16)&(C[:,2]>=0)&(C[:,2]<=16)
    cover[g]=dict(cells_in_box=int(inb.sum()),cells_sampled=int(len(np.unique(idx))),median_dist=float(np.median(dist)),max_dist=float(dist.max()))
    v3=(C[:,0]>=8)&(C[:,0]<=48)&(np.abs(C[:,1])<=12)&(C[:,2]>=0)&(C[:,2]<=12)
    gg=grad[g]; boxes[g]=dict(v1=float(gg.sum()),v2_box=float(gg[inb].sum()),v2_pos=float(gg[inb&(gg>0)].sum()),v2_neg=float(gg[inb&(gg<0)].sum()),v3_box=float(gg[v3].sum()),n_v2=int(inb.sum()),n_v3=int(v3.sum()))
a,b=rho['中'],rho['细']
pr=pearsonr(a,b)[0]; sr=spearmanr(a,b)[0]
def top(r): k=int(np.ceil(0.05*len(r))); return set(np.argsort(-np.abs(r))[:k])
ta,tb=top(a),top(b); inter=ta&tb; jac=len(inter)/len(ta|tb)
sign=np.mean(np.sign(a[list(inter)])==np.sign(b[list(inter)])) if inter else float('nan')
co=(jac>=0.5) and (sign>=0.8)
verdict='局部梯度分布跨网格稳定' if (pr>=0.8 and co) else ('不稳定，建议止于 G1' if pr<0.5 else '不判')
out=dict(cover=cover,boxes=boxes,top5_k=int(len(ta)),top5_intersection=int(len(inter)),top5_union=int(len(ta|tb)),points=int(len(P)),pearson=float(pr),spearman=float(sr),top5_jaccard=float(jac),top5_sign_agree=float(sign),co_located=bool(co),verdict=verdict)
json.dump(out,open(H+'/spatial_corr_v2_numbers.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
# 图：z=4 m 与 z=10 m 水平切片
fig,axs=plt.subplots(2,2,figsize=(9,8))
for r,zc in enumerate((4.25,10.25)):
    m=np.isclose(P[:,2],zc)
    lim=np.percentile(np.abs(np.r_[rho['中'][m],rho['细'][m]]),99) or 1
    for c,g in enumerate(('中','细')):
        v=rho[g][m]
        sc=axs[r,c].scatter(P[m,0],P[m,1],c=v,s=6,cmap='RdBu_r',vmin=-lim,vmax=lim,marker='s')
        axs[r,c].add_patch(plt.Rectangle((-8,-8),16,16,fill=False,ec='k',lw=1)) if zc<8 else None
        axs[r,c].set_title(f'{g}网格，z={zc:.2f} m（两档同色标）'); axs[r,c].set_aspect('equal'); plt.colorbar(sc,ax=axs[r,c],shrink=0.8)
fig.suptitle(f'梯度密度 ∂Cp/∂β/V（建筑周围盒）  Pearson={pr:.3f}，前5%重叠={jac:.3f}，符号一致={sign:.2f}')
fig.text(0.01,0.01,'数据来源：本线 DAFoam v5.1.1 CRC 计算（L26.21 网格收敛检验）；来流沿 +x',fontsize=6.5)
fig.tight_layout(rect=(0,0.03,1,0.96)); fig.savefig(H+'/spatial_corr_v2_slices.png',dpi=130); plt.close(fig)
fig,ax=plt.subplots(figsize=(5.5,5)); lim=np.percentile(np.abs(np.r_[a,b]),99.5)
ax.scatter(a,b,s=2,alpha=0.3); ax.plot([-lim,lim],[-lim,lim],'k--',lw=0.8); ax.set_xlim(-lim,lim); ax.set_ylim(-lim,lim)
ax.set_xlabel('中网格 ρ'); ax.set_ylabel('细网格 ρ'); ax.set_title(f'同点梯度密度对比  Pearson={pr:.2f}')
fig.tight_layout(); fig.savefig(H+'/spatial_corr_v2_scatter.png',dpi=130); plt.close(fig)
