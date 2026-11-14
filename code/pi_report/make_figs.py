# 从 L26.12 结果文件程序化生成给 Liang Hu 报告用的两张图与汇总数字（不重算任何模型）
import json, statistics, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Noto Sans CJK SC','WenQuanYi Zen Hei','SimHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
recs=[json.loads(l) for f in ['step2/interventions_complete.jsonl','step3/interventions_remaining.jsonl'] for l in open(f)]
feats=[230,270,991,1004,1199]; alphas=[0.0,0.5,1.5,2.0]
out={}
fig,axs=plt.subplots(1,5,figsize=(16,3.4),sharey=True)
for ax,k in zip(axs,feats):
    E=[statistics.median([r['dmsl_hpa'] for r in recs if r['control']=='target' and r['feature']==k and r['alpha']==a]) for a in alphas]
    ctrl=sorted({r['feature'] for r in recs if r['control']=='matched' and r['reference']==k})
    def e0(a):
        v=[[r['dmsl_hpa'] for r in recs if r['control']=='matched' and r['reference']==k and r['feature']==c and r['alpha']==a] for c in ctrl]
        v=[abs(statistics.median(x)) for x in v if x]
        return float(np.percentile(v,95)) if v else None
    E0=[e0(a) for a in alphas]
    n=len({r['sid'] for r in recs if r['control']=='target' and r['feature']==k})
    out[k]={'E':E,'E0':E0,'n_storms':n,'n_ctrl':len(ctrl)}
    ea=[a for a,e in zip(alphas,E0) if e is not None]; ev=[e for e in E0 if e is not None]
    ax.errorbar(ea,[0]*len(ea),yerr=ev,fmt='none',ecolor='0.5',capsize=6,lw=6,alpha=0.4,label='对照特征 |E| 95 分位（α=0、2）')
    ax.plot(alphas,E,'o-',color='C3',label='目标特征 E（中位）')
    ax.axhline(0,color='k',lw=0.5); ax.set_title(f'特征 {k}（{n} 场）'); ax.set_xlabel('倍数 α（0=删除，2=加倍）')
axs[0].set_ylabel('24 h 最低气压变化（hPa）'); axs[0].legend(fontsize=7,loc='lower left')
fig.suptitle('图 1  单特征干预前后 24 h 台风最低气压变化（Pangu 主干层，2021 年留出风暴，跨风暴中位）',fontsize=10)
fig.tight_layout(); fig.savefig('pi_report/图1_干预效应.png',dpi=130)
pd=[r['dmsl_hpa'] for r in recs if r['control']=='pure_decoder']; out['pure_decoder_median']=statistics.median(pd); out['pure_decoder_n']=len(pd)
b=json.load(open('step3/b_results.json'))
rows=[('原 200/1000 次',b['legacy']['pres_hpa'])]+[(f"种子 {s['seed']}",s) for s in b['expanded']['pres_hpa']]
fig,ax=plt.subplots(figsize=(7,3.6)); xs=np.arange(len(rows)); g={}
for i,(lab,blk) in enumerate(rows):
    c={x['feature']:x for x in blk['candidates']}
    lb991=abs(c[991]['ci'][1]); lb270=abs(c[270]['ci'][1])
    g[lab]={'lb991':lb991,'lb270':lb270,'perm_max':blk['null']['maximum'],'perm_q95':blk['null']['q95']}
    ax.plot(i-0.1,lb991,'o',color='C3'); ax.plot(i+0.1,lb270,'s',color='C1')
    ax.plot([i-0.3,i+0.3],[blk['null']['maximum']]*2,'k-'); ax.plot([i-0.3,i+0.3],[blk['null']['q95']]*2,'k--')
ax.plot([],[],'o',color='C3',label='特征 991 相关区间下界'); ax.plot([],[],'s',color='C1',label='特征 270 相关区间下界')
ax.plot([],[],'k-',label='门槛：置换最大值（主读法）'); ax.plot([],[],'k--',label='门槛：置换 95 分位（并列读法）')
ax.set_xticks(xs); ax.set_xticklabels([r[0] for r in rows]); ax.set_ylabel('|ρ|（与最低气压）'); ax.set_ylim(0.5,0.75); ax.legend(fontsize=7,loc='lower right')
ax.set_title('图 2  相关关：最好特征的区间下界与两种门槛（2021 年 46 场留出风暴）',fontsize=10)
fig.tight_layout(); fig.savefig('pi_report/图2_相关门槛.png',dpi=130)
out['B']=g
json.dump(out,open('pi_report/figs_numbers.json','w'),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False,indent=1))
