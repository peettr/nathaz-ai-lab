"""L26.21 meshconv 第⑥栏补充诊断：(1) 线性化 ΔCp 量级；(2) 逐单元梯度分布（单元中心/体积未存档，无空间比较）。"""
import gzip, io, json, numpy as np, os
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('./Windows/Fonts/NotoSansSC-VF.ttf'); plt.rcParams['font.family']='Noto Sans SC'; plt.rcParams['axes.unicode_minus']=False
H=os.path.dirname(os.path.abspath(__file__)); R=H+'/../returned_v2'
def jl(p): return json.load(gzip.open(p,'rt'))
def npy(p): return np.load(io.BytesIO(gzip.open(p).read()))
grads={'粗':npy(H+'/coarse_gradient.npy.gz'),'中':npy(H+'/medium_gradient.npy.gz'),'细':npy(H+'/fine_gradient_final.npy.gz')}
dirs={'粗':jl(R+'/coarse/0005_meshconv_directions.json.gz'),'中':jl(R+'/medium/0005_meshconv_directions.json.gz'),'细':jl(R+'/fine/0022_meshconv_directions.json.gz')}
cp={'粗':jl(R+'/coarse/0005_g1_gate.json.gz')['cp'],'中':jl(R+'/medium/0005_g1_gate.json.gz')['cp'],'细':jl(R+'/fine/0022_g1_gate.json.gz')['cp']}
out={'cp':cp}
def dval(d,k):
    for kk,v in d.items():
        if k in kk and isinstance(v,(int,float)): return v
        if k in kk and isinstance(v,dict):
            for k2 in ('value','adjoint','dot'):
                if k2 in v: return v[k2]
    return None
# 方向值
D={g:{k:[v['adjoint_dot'] for kk,v in d['directions'].items() if kk.startswith(k)][0] for k in ('v1','v2','v3')} for g,d in dirs.items()}
out['directional']=D
grid=abs(cp['细']-cp['中']); out['grid_diff_med_fine']=grid
out['dCp_beta+0.1']={g:{k:(0.1*v if isinstance(v,(int,float)) else None) for k,v in D[g].items()} for g in D}
# 逐单元分布
st={}
for g,a in grads.items():
    a=a.ravel(); st[g]=dict(n=int(a.size),sum=float(a.sum()),sum_abs=float(np.abs(a).sum()),pos=float(a[a>0].sum()),neg=float(a[a<0].sum()),
        cancel_ratio=float(abs(a.sum())/np.abs(a).sum()),max_abs=float(np.abs(a).max()),p99_abs=float(np.percentile(np.abs(a),99)),
        top1pct_share=float(np.sort(np.abs(a))[::-1][:max(1,a.size//100)].sum()/np.abs(a).sum()))
out['cell_stats']=st
json.dump(out,open(H+'/diag_numbers.json','w'),ensure_ascii=False,indent=1,default=float)
# 图1 ΔCp 量级
fig,ax=plt.subplots(figsize=(7.5,4.2)); labs=['v1 全场','v2 建筑周围','v3 尾流']; x=np.arange(3); w=0.25
for i,(g,c) in enumerate(zip(['粗','中','细'],['#9bbb59','#4f81bd','#1f497d'])):
    v=[abs(out['dCp_beta+0.1'][g][k]) for k in ('v1','v2','v3')]; ax.bar(x+(i-1)*w,v,w,label=f'{g}网格',color=c)
ax.axhline(grid,ls='--',c='#c0504d'); ax.text(2.45,grid*1.15,f'屋面 Cp 中→细网格差 {grid:.1e}',ha='right',fontsize=8,color='#c0504d')
ax.axhline(0.1,ls=':',c='k'); ax.text(2.45,0.115,'实测目标离散约 ±0.1（Silsoe）',ha='right',fontsize=8)
ax.set_yscale('log'); ax.set_xticks(x); ax.set_xticklabels(labs); ax.set_ylabel('|ΔCp|（区域内 β 整体 +0.1，线性化）'); ax.legend(fontsize=8)
ax.set_title('方向灵敏度量级 vs 网格差与实测不确定度')
fig.text(0.01,0.01,'数据来源：本线 DAFoam v5.1.1 CRC 计算（L26.21 网格收敛检验）',fontsize=6.5); fig.tight_layout(rect=(0,0.04,1,1)); fig.savefig(H+'/diag_fig1_dCp_magnitude.png',dpi=150); plt.close(fig)
# 图2 逐单元梯度分布
fig,ax=plt.subplots(figsize=(7.5,4.2)); bins=np.logspace(-16,-3,66)
for g,c in zip(['粗','中','细'],['#9bbb59','#4f81bd','#1f497d']):
    a=grads[g].ravel(); ax.hist(np.abs(a[a>0]),bins=bins,histtype='step',color=c,label=f'{g} 正',lw=1.4); ax.hist(np.abs(a[a<0]),bins=bins,histtype='step',color=c,ls='--',label=f'{g} 负',lw=1.2)
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('|∂Cp/∂β_i|（逐单元，未除体积）'); ax.set_ylabel('单元数'); ax.legend(fontsize=7,ncol=3)
ax.set_title('逐单元伴随梯度量级分布（单元中心/体积未存档，无法做空间对比）')
fig.text(0.01,0.01,'数据来源：本线 DAFoam v5.1.1 CRC 计算（L26.21 网格收敛检验）',fontsize=6.5); fig.tight_layout(rect=(0,0.04,1,1)); fig.savefig(H+'/diag_fig2_cell_gradient_hist.png',dpi=150); plt.close(fig)
print(json.dumps(out,ensure_ascii=False,indent=1,default=float))
