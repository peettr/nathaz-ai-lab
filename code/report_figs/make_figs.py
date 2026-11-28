# L26.28 网站报告配图：全部数字读自 D1/metrics.json
import json, sys, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fp = fm.FontProperties(fname='./Windows/Fonts/simsun.ttc'); fm.fontManager.addfont(fp.get_file()); plt.rcParams['font.family']=fp.get_name(); plt.rcParams['axes.unicode_minus']=False
M = json.load(open(sys.argv[1])); OUT = sys.argv[2]
SRC = '数据：Zhao 等 2026 随包检验输出（Zenodo 10.5281/zenodo.19205784）；IBTrACS v04r01 最佳路径'
met = M['metrics']; LEADS=['12h','24-72h','96-168h']; AG=['CMA','JTWC','JMA']; COL={'CMA':'#1f6fb4','JTWC':'#d4572a','JMA':'#8a8a8a'}
def foot(fig): fig.text(0.01,0.01,SRC,fontsize=7,color='#555')
# 图1 R
for var,name,unit,fn in [('P','最低气压','hPa','fig1_R_pressure.png'),('V','最大风','m/s','fig2_R_wind.png')]:
    fig,ax=plt.subplots(1,2,figsize=(10,4.2))
    for k,a in enumerate(AG):
        xs=[i+(k-1)*0.25 for i in range(3)]
        R=[met[L]['agencies'][a][var]['R'] for L in LEADS]
        ax[0].bar(xs,R,0.25,color=COL[a],label=a+('（只报告）' if a=='JMA' else ''))
        D=[met[L]['agencies'][a][var]['bootstrap']['difference_sr_minus_pangu'] for L in LEADS]
        lo=[met[L]['agencies'][a][var]['bootstrap']['ci90'][0] for L in LEADS]; hi=[met[L]['agencies'][a][var]['bootstrap']['ci90'][1] for L in LEADS]
        ax[1].errorbar(xs,D,yerr=[[d-l for d,l in zip(D,lo)],[h-d for d,h in zip(D,hi)]],fmt='o',color=COL[a],capsize=3)
    for t in (0.8,0.95): ax[0].axhline(t,ls='--',color='k',lw=0.8)
    ax[0].text(-0.45,0.78,'0.8 优于线',fontsize=8,va='top',ha='left'); ax[0].text(-0.45,0.97,'0.95 无实质改进线',fontsize=8,va='bottom',ha='left')
    ax[0].axhline(1,color='#bbb',lw=0.6); ax[1].axhline(0,color='k',lw=0.8)
    for a_ in ax: a_.set_xticks(range(3)); a_.set_xticklabels(['12 h','24–72 h','96–168 h'])
    ax[0].set_ylabel(f'R = MAE(HybSR)/MAE(Pangu)'); ax[0].set_title(f'{name}：误差比 R'); ax[0].legend(fontsize=8)
    ax[1].set_ylabel(f'Δ = MAE(HybSR) - MAE(Pangu)（{unit}）'); ax[1].set_title(f'{name}：Δ 与台风整组自助 90% 区间')
    fig.tight_layout(rect=(0,0.04,1,1)); foot(fig); fig.savefig(os.path.join(OUT,fn),dpi=130); plt.close(fig)
# 图3 分档风偏差
mech=M['mechanism']; bins=['<33','33-50','>=50']; lab={'<33':'<33 m/s','33-50':'33–50 m/s','>=50':'≥50 m/s'}
fig,ax=plt.subplots(figsize=(8,4.2)); x=0
ticks=[];tl=[]
for L in ['24-72h','96-168h']:
    for b in bins:
        d=mech[L][b]
        if not d['n']: continue
        ax.bar(x-0.2,d['pangu_wind_bias_ms'],0.4,color='#999',label='Pangu' if x==0 else None)
        ax.bar(x+0.2,d['sr_wind_bias_ms'],0.4,color='#1f6fb4',label='HybSR' if x==0 else None)
        ticks.append(x); tl.append(f"{L.replace('h',' h').replace('-','–')}\n{lab[b]}\nn={d['n']}"); x+=1
    x+=0.5
ax.axhline(0,color='k',lw=0.8); ax.set_xticks(ticks); ax.set_xticklabels(tl,fontsize=8); ax.set_ylabel('最大风平均偏差（模型-CMA，m/s）')
ax.set_title('按 CMA 同刻强度分档的最大风偏差'); ax.legend(fontsize=8); fig.tight_layout(rect=(0,0.04,1,1)); foot(fig); fig.savefig(os.path.join(OUT,'fig3_bias_by_intensity.png'),dpi=130); plt.close(fig)
# 图4 峰值
pk=M['peaks']; names=sorted(pk,key=lambda n:pk[n]['CMA_peak_ms'])
fig,ax=plt.subplots(figsize=(8,4.5)); y=range(len(names))
ax.barh([i-0.2 for i in y],[pk[n]['median_pangu_error_ms'] for n in names],0.4,color='#999',label='Pangu')
ax.barh([i+0.2 for i in y],[pk[n]['median_sr_error_ms'] for n in names],0.4,color='#1f6fb4',label='HybSR')
ax.set_yticks(list(y)); ax.set_yticklabels([f"{n.title()}（峰值 {pk[n]['CMA_peak_ms']:.0f} m/s）" for n in names],fontsize=8)
ax.axvline(0,color='k',lw=0.8); ax.set_xlabel('峰时 ±12 h 内模型最大风 - CMA 峰值（m/s，5 个起报中位）'); ax.set_title('各台风峰值强度误差'); ax.legend(fontsize=8)
fig.tight_layout(rect=(0,0.04,1,1)); foot(fig); fig.savefig(os.path.join(OUT,'fig4_peak_error.png'),dpi=130); plt.close(fig)
# 图5 可得性示意（只用已核事实，文字）
fig,ax=plt.subplots(figsize=(8,3.6)); ax.axis('off')
rows=[('作者随包检验强度表（10 台风×5 起报）','可得，已用'),('最佳路径 CMA / JTWC / JMA','可得，已用（JMA 只报告）'),
      ('检验台风 2 km 空间风场（带时刻与中心）','不可得：只有径向平均剖面'),('卫星雷达（SAR）可配对景','0 景（模型侧无空间场）'),
      ('HybSR 生成器权重（两版代码包）','不可得'),('随包输出所用训练配置','无法确证；一套配置的训练列表含检验台风编号')]
for i,(a,b) in enumerate(rows):
    ok=b.startswith('可得'); ax.text(0.02,0.9-i*0.15,a,fontsize=10); ax.text(0.62,0.9-i*0.15,b,fontsize=10,color='#1a7f37' if ok else '#b42318')
ax.set_title('数据与工具可得性（D0 核查）'); foot(fig); fig.savefig(os.path.join(OUT,'fig5_availability.png'),dpi=130); plt.close(fig)
print('ok')
