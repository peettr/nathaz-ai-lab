"""S3a 网站报告配图。用法: python3 -I s3a_report_figs.py <TS_dir> <SYN_dir> <s3a_v2.json> <figs_dir>"""
import sys,json,numpy as np,matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
TSD,SYD,J,F=sys.argv[1:5]
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s3a_v2_analyze.py').read().split('out={}')[0].replace('TSD,SYD,OUT=sys.argv[1:4]','TSD,SYD,OUT=None,None,None'),'defs','exec'),ns)
plt.rcParams.update({'font.family':'WenQuanYi Zen Hei','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#8a8984','axes.labelcolor':'#0b0b0b','xtick.color':'#52514e','ytick.color':'#52514e','axes.grid':True,'grid.color':'#e6e5e0','grid.linewidth':0.6,'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','savefig.dpi':150})
C={'TS':'#eb6834','SYN':'#2a78d6'};LAB={'TS':'雷暴','SYN':'良态大风'}
d=json.load(open(J));Ts=[10,20,30]
# fig1 memory & noise share vs T
fig,ax=plt.subplots(1,2,figsize=(8.4,3.4))
for k in ('TS','SYN'):
    for a,key,ttl in ((ax[0],'d_mem','记忆份额 Δ_mem = R²_MZ - R²_M'),(ax[1],'noise','噪声份额 = 1 - R²_MZ')):
        y=[d[str(T)][k][key] for T in Ts];a.plot(Ts,y,'-o',color=C[k],lw=2,ms=6,label=LAB[k]);a.set_title(ttl,fontsize=10,loc='left');a.set_xlabel('解析层平均时距 T（min）');a.set_xticks(Ts)
ax[0].set_ylim(-0.01,0.4);ax[1].set_ylim(-0.01,0.4);ax[0].legend(frameon=False)
for a in ax:a.axhline(0,color='#8a8984',lw=0.8)
fig.tight_layout();fig.savefig(F+'/fig2_memory_vs_noise.png');plt.close()
# fig budget T=10 stacked horizontal
fig,a=plt.subplots(figsize=(7.8,2.8))
for i,k in enumerate(('SYN','TS')):
    m=d['10'][k]['M'];dm=max(d['10'][k]['d_mem'],0);nz=d['10'][k]['noise'];left=0
    for v,col,nm in ((m,'#c9c8c2','当前平均风可解释 R²_M'),(dm,'#6250d6','记忆 Δ_mem'),(nz,C[k],'噪声 1-R²_MZ')):
        a.barh(i,v,left=left,color=col,height=0.55,edgecolor='#fcfcfb',linewidth=2,label=nm if (i==1 or col=='#c9c8c2') and i==1 else None);left+=v
    a.text(1.01,i,f'噪声 {nz:.3f}，记忆 {d["10"][k]["d_mem"]:.4f}',va='center',fontsize=9,color='#52514e')
from matplotlib.patches import Patch;a.legend(handles=[Patch(color='#c9c8c2',label='当前平均风可解释 R²_M'),Patch(color='#6250d6',label='记忆 Δ_mem（两组都 <0.003，几乎看不见）'),Patch(color='#8a8984',label='噪声 1-R²_MZ（按组着色）')],frameon=False,fontsize=8,loc='lower center',bbox_to_anchor=(0.5,1.0),ncol=3);a.set_yticks([0,1]);a.set_yticklabels([LAB['SYN'],LAB['TS']]);a.set_xlim(0,1.45);a.set_xticks([0,.25,.5,.75,1]);a.set_xlabel('阵风 G 的方差份额（T=10 min，交叉验证）');a.grid(axis='y',visible=False)
fig.tight_layout();fig.savefig(F+'/fig1_variance_budget.png');plt.close()
# windows
Wt,_=ns['windows'](TSD,'TS');Ws,_=ns['windows'](SYD,'SYN')
# fig example series
def pick(W,mode):
    sc=[(np.nanmax(g),np.nanmean(s),i) for i,(n,s,g) in enumerate(W)]
    if mode=='max':return W[max(sc)[2]]
    sc=sorted(sc,key=lambda x:x[1]);return W[sc[len(sc)//2][2]]
fig,ax=plt.subplots(2,1,figsize=(8.4,5.0),sharex=True)
for a,(k,W,mode) in zip(ax,(('TS',Wt,'max'),('SYN',Ws,'med'))):
    n,s,g=pick(W,mode);t=np.arange(361)/60-3;U,G=ns['blocks'](s,g,10);tb=(np.arange(len(U))*10+5)/60-3
    a.plot(t,s,color='#9a9993',lw=1,label='2 min 平均风（逐分钟）');a.plot(t,g,color=C[k],lw=1,alpha=0.8,label='最大 5 s 风（逐分钟）')
    a.step(np.r_[tb-5/60,tb[-1]+5/60],np.r_[U,U[-1]],where='post',color='#0b0b0b',lw=1.6,label='10 min 块均值 U')
    a.plot(tb,G,'o',color=C[k],ms=5,markeredgecolor='#fcfcfb',label='10 min 块最大 G');a.set_ylabel('风速（节）');a.set_title(f'{LAB[k]}示例窗（窗中心时刻 = 0）',fontsize=10,loc='left')
ax[0].legend(frameon=False,fontsize=8,ncol=2);ax[1].set_xlabel('相对窗中心的时间（h）')
fig.tight_layout();fig.savefig(F+'/fig3_example_windows.png');plt.close()
# fig rho exceedance
fig,a=plt.subplots(figsize=(6.4,3.8))
for k,W in (('TS',Wt),('SYN',Ws)):
    r=np.sort(np.concatenate(ns['rho'](W,10)));p=1-np.arange(len(r))/len(r);a.semilogy(r,p,color=C[k],lw=2,label=f'{LAB[k]}（n={len(r)}）')
    q=d['rho_all'][k+'_q99'];a.axvline(q,color=C[k],lw=0.8,ls='--')
a.axhline(0.01,color='#8a8984',lw=0.8);a.text(3.6,0.012,'超越概率 1%',fontsize=8,color='#52514e',ha='right')
from matplotlib.ticker import FixedLocator,FixedFormatter;a.yaxis.set_major_locator(FixedLocator([1,0.1,0.01,0.001]));a.yaxis.set_major_formatter(FixedFormatter(['1','0.1','0.01','0.001']));a.yaxis.set_minor_formatter(FixedFormatter([]));a.set_xlabel('阵风比 ρ = G / U（T=10 min，U ≥ 10 节）');a.set_ylabel('超越概率 P(ρ > x)');a.set_xlim(1,3.7);a.legend(frameon=False)
fig.tight_layout();fig.savefig(F+'/fig4_gust_ratio_exceedance.png');plt.close()
# fig strata q99
fig,a=plt.subplots(figsize=(6.6,3.6));st=['10-15','15-20','20-inf'];lab=['10–15 节','15–20 节','≥ 20 节'];x=np.arange(3)
for j,k in enumerate(('SYN','TS')):
    a.bar(x+(j-0.5)*0.34,[d['rho_strata'][s][k+'_q99'] for s in st],width=0.32,color=C[k],label=LAB[k],edgecolor='#fcfcfb',linewidth=2)
for i,s in enumerate(st):
    o=d['rho_strata'][s]['dq99'];a.text(i,max(d['rho_strata'][s]['TS_q99'],d['rho_strata'][s]['SYN_q99'])+0.08,f"差 {o['pt']:.2f}\n[{o['ci'][0]:.2f}, {o['ci'][1]:.2f}]",ha='center',fontsize=8,color='#52514e')
a.set_xticks(x);a.set_xticklabels(lab);a.set_xlabel('块均值 U 分层');a.set_ylabel('ρ 的 99% 分位');a.set_ylim(0,3.8);a.legend(frameon=False,loc='upper right');a.grid(axis='x',visible=False)
fig.tight_layout();fig.savefig(F+'/fig5_strata_q99.png');plt.close()
print('ok')
