import csv, sys, statistics as st
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')
plt.rcParams['font.family']='WenQuanYi Zen Hei'; plt.rcParams['axes.unicode_minus']=False
sys.path.insert(0,'./22_Lab/06_Logs/luw')
L='./22_Lab/06_Logs/luw/'
src=open(L+'digitize_han_fig1d.py').read()
ns={}; exec(src.split('assert')[0],ns)
order,paper=ns['order'],ns['paper']; P=dict(zip(order,paper))
r={int(float(x['id'])):x for x in csv.DictReader(open(L+'CaseE_W_points_full_r7.csv'))}
wt=[float(r[i]['after']) for i in order]; pp=[P[i] for i in order]
ov=[float(r[i]['s_cfd_shift']) for i in order]; os_=[float(r[i]['s_exp_shift']) for i in order]
mae=lambda a,b: sum(abs(x-y) for x,y in zip(a,b))/len(a)
INK='#2b2b2b'; MUTED='#6b6b66'; GRID='#e4e3df'
C_P='#eb6834'; C_V='#2a78d6'; C_S='#1baf7a'
x=list(range(80))
groups=[(0,23,'尾流区 + 近楼'),(24,33,'尾流区 + 远楼'),(34,44,'非尾流 + 远楼'),(45,79,'非尾流 + 近楼')]
fig,axs=plt.subplots(3,1,figsize=(16,11),sharex=True,gridspec_kw=dict(height_ratios=[1.5,1,1],hspace=0.12))
for ax in axs:
    for k,(a,b,_) in enumerate(groups):
        if k in (0,2): ax.axvspan(a-0.5,b+0.5,color='#f1f0ec',zorder=0)
    ax.grid(axis='y',color=GRID,lw=0.8); ax.set_axisbelow(True)
    for s in ('top','right'): ax.spines[s].set_visible(False)
    for s in ('left','bottom'): ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)
ax=axs[0]
ax.plot(x,wt,'-s',color=INK,ms=6,lw=1.6,label='风洞实测（改造后·西风）',zorder=5)
ax.plot(x,pp,'-o',color=C_P,ms=6,lw=1.4,mfc='white',mew=1.6,label=f'论文 LUW（图 1(d) 读数）  对实测 MAE {mae(pp,wt):.3f}',zorder=4)
ax.plot(x,ov,'-^',color=C_V,ms=6,lw=1.4,label=f'我们·矢量口径（与论文同口径）  MAE {mae(ov,wt):.3f}',zorder=3)
ax.plot(x,os_,'-D',color=C_S,ms=5,lw=1.4,label=f'我们·标量口径（加湍动能）  MAE {mae(os_,wt):.3f}',zorder=3)
ax.set_ylabel('U / Uref（15.9 m 入流）',color=INK); ax.set_ylim(0,1.45)
for a,b,t in groups: ax.text((a+b)/2,1.40,t,ha='center',va='top',fontsize=10,color=MUTED)
ax.legend(loc='upper right',bbox_to_anchor=(1,0.93),frameon=False,fontsize=10)
ax.set_title('AIJ Case E（西风，80 个 2 m 测点）：风洞、论文与我们的逐点对比',loc='left',fontsize=14,color=INK)
ax=axs[1]
ax.axhline(0,color=INK,lw=1)
ax.plot(x,[a-b for a,b in zip(pp,wt)],'-o',color=C_P,ms=5,lw=1.2,mfc='white',mew=1.4,label='论文 - 实测')
ax.plot(x,[a-b for a,b in zip(ov,wt)],'-^',color=C_V,ms=5,lw=1.2,label='我们矢量 - 实测')
ax.plot(x,[a-b for a,b in zip(os_,wt)],'-D',color=C_S,ms=4,lw=1.2,label='我们标量 - 实测')
ax.set_ylabel('与实测的差',color=INK); ax.set_ylim(-0.75,0.75)
ax.legend(loc='upper right',ncol=3,frameon=False,fontsize=10)
ax=axs[2]
ax.axhline(0,color=INK,lw=1)
ax.plot(x,[a-b for a,b in zip(ov,pp)],'-^',color=C_V,ms=5,lw=1.2,label=f'我们矢量 - 论文  平均绝对差 {mae(ov,pp):.3f}')
ax.plot(x,[a-b for a,b in zip(os_,pp)],'-D',color=C_S,ms=4,lw=1.2,label=f'我们标量 - 论文  平均绝对差 {mae(os_,pp):.3f}')
ax.set_ylabel('与论文的差',color=INK); ax.set_ylim(-0.75,0.75)
ax.legend(loc='upper right',ncol=2,frameon=False,fontsize=10)
ax.set_xticks(x); ax.set_xticklabels([str(i) for i in order],rotation=90,fontsize=8)
ax.set_xlabel('测点编号（按论文图 1(d) 的顺序与分组）',color=INK)
fig.text(0.01,0.005,'来源：风洞 = AIJ Case E 官方数据（改造后，西风，按 15.9 m 入流风速归一）；论文 = Han et al. 2026, arXiv 2607.04516v2 图 1(d) 人工读数（每点约 ±0.05）；'
 '我们 = 公开 LUW dd438c1，1 m 网格，约 500 m 域，第七轮，(+1,+1,0) m 配准。',fontsize=8.5,color=MUTED)
out=L+'CaseE_W_ours_vs_paper_vs_WT_r7.png'; fig.savefig(out,dpi=140,bbox_inches='tight'); print(out)
# group table
for a,b,t in groups:
    s=slice(a,b+1)
    print(t, b-a+1, 'paper',round(mae(pp[s],wt[s]),3),'vec',round(mae(ov[s],wt[s]),3),'sca',round(mae(os_[s],wt[s]),3),'vec-paper',round(mae(ov[s],pp[s]),3),
      'meanWT',round(st.mean(wt[s]),2),'meanP',round(st.mean(pp[s]),2),'meanV',round(st.mean(ov[s]),2),'meanS',round(st.mean(os_[s]),2))
