#!/usr/bin/env python3
"""Figures + numbers for public report 20261118_R21.4_caseE_error_pattern. Reads only verified T10a inputs."""
import sys,json,math,csv
from pathlib import Path
L=Path('./24_Urban_Wind_LBM/06_Logs')
sys.path.insert(0,str(L/'R21.4a_T10a_error_structure'))
import analyze as A
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for fp in ('./Windows/Fonts/msyh.ttc','./Windows/Fonts/simhei.ttf'):
  try: fm.fontManager.addfont(fp)
  except Exception: pass
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
OUT=Path(sys.argv[1]);(OUT/'figs').mkdir(parents=True,exist_ok=True)
W=A.load_widths()
cfg={'off_s100':A.from_t2c('baseline_1m'),'off_s103':A.from_t2d()}
cfg['fine_0p5']={int(r['id']):(float(r['fine']['primary']['Su'])/A.U,float(r['obs'])) for r in A.read(A.T2) if r['h_wall_m']==2.0}
for s in (101,102):
  for lab,base,st in [('off',A.T5,'off'),('T5_on',A.T5,'on'),('T6_on',A.T6,'on'),('T7',A.T7,'off'),('T9b_on',A.T9,'on')]:
    cfg[f'{lab}_s{s}']=A.rows_points(base/f'E_s{s}_{st}_points80.json')
ids=sorted(W); cover={i:float(W[i]['disk50_cover']) for i in ids}
med=sorted(cover.values())[39:41]; med=sum(med)/2
dense={i for i in ids if cover[i]>=med}
def stats(d):
  p=[d[i][0] for i in ids];o=[d[i][1] for i in ids]
  a=sum(x*y for x,y in zip(p,o))/sum(x*x for x in p)
  mse=sum((x-y)**2 for x,y in zip(p,o))/80; pat=sum((a*x-y)**2 for x,y in zip(p,o))/80
  e={i:a*d[i][0]-d[i][1] for i in ids}
  C=sum(e[i] for i in ids if i not in dense)/40-sum(e[i] for i in dense)/40
  mae=sum(abs(x-y) for x,y in zip(p,o))/80
  return dict(a=a,MSE=mse,MSE_pat=pat,phi=pat/mse,C=C,MAE=mae,e=e)
S={k:stats(v) for k,v in cfg.items()}
seeds=['off_s100','off_s101','off_s102','off_s103']
Rpat=max(S[k]['MSE_pat'] for k in seeds)-min(S[k]['MSE_pat'] for k in seeds)
Cr=max(S[k]['C'] for k in seeds)-min(S[k]['C'] for k in seeds)
# check against frozen results
T10a=json.load(open(L/'R21.4a_T10a_error_structure/T10a_result.json'))
assert abs(T10a['R_pat']-Rpat)<1e-12
for k in seeds: assert abs(T10a['metrics'][k]['all80']['phi']-S[k]['phi'])<1e-12
T10b=json.load(open(L/'R21.4a_T10b_contrast/T10b_result.json'))
for k in seeds: assert abs(T10b['configs'][k]['C']-S[k]['C'])<1e-12,k
num={'Rpat':Rpat,'C_range':Cr,'seeds':{k:{x:S[k][x] for x in ('a','MSE','MSE_pat','phi','C','MAE')} for k in seeds}}
# fig1 map
s0=S['off_s100']['e'];x=[float(W[i]['x_m']) for i in ids];y=[float(W[i]['y_m']) for i in ids]
fig,ax=plt.subplots(figsize=(6.4,5.6));v=max(abs(s0[i]) for i in ids)
sc=ax.scatter(x,y,c=[s0[i] for i in ids],cmap='RdBu_r',vmin=-v,vmax=v,s=60,marker='o',edgecolors=['k' if i in dense else 'none' for i in ids],linewidths=0.8)
plt.colorbar(sc,ax=ax,label='格局残差 e = a·p − o（红：模型偏快，蓝：偏慢）')
ax.set_aspect('equal');ax.set_xlabel('x (m)');ax.set_ylabel('y (m)');ax.set_title('Case E 80 个测点的格局残差（1 m，种子 1；黑圈＝建筑覆盖率高的一半）',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'figs/fig1_residual_map.png',dpi=150);plt.close()
# fig2 scatter
fig,ax=plt.subplots(figsize=(5.2,5.0));d=cfg['off_s100'];a=S['off_s100']['a']
for grp,col,lab in [(dense,'#2b6cb0','建筑覆盖率高（密，40 点）'),(set(ids)-dense,'#d9822b','建筑覆盖率低（疏，40 点）')]:
  ax.scatter([d[i][1] for i in grp],[a*d[i][0] for i in grp],c=col,s=22,label=lab)
m=max(max(v) for v in d.values())*1.05;ax.plot([0,m],[0,m],'k--',lw=0.8,label='1:1')
ax.set_xlabel('风洞实测 风速比 o');ax.set_ylabel('模型 风速比 a·p（已扣整体比例）');ax.legend(fontsize=8);ax.set_title(f'模型与风洞逐点对比（1 m，种子 1，a = {a:.3f}）',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'figs/fig2_scatter.png',dpi=150);plt.close()
# fig3 e vs cover
fig,ax=plt.subplots(figsize=(6.0,4.2));mk=['o','s','^','D']
for k,mm in zip(seeds,mk):
  e=S[k]['e'];ax.scatter([cover[i] for i in ids],[e[i] for i in ids],s=14,marker=mm,alpha=0.6,label='种子 '+str(seeds.index(k)+1))
ax.axvline(med,color='gray',ls=':',lw=1);ax.axhline(0,color='k',lw=0.6)
ax.set_xlabel('测点周围 50 m 内建筑覆盖率');ax.set_ylabel('格局残差 e');ax.legend(fontsize=8,ncol=2);ax.set_title('残差随周边建筑密度变化（4 个随机种子；虚线＝中位数分组线）',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'figs/fig3_residual_vs_cover.png',dpi=150);plt.close()
# fig4 phi & C
fig,axs=plt.subplots(1,2,figsize=(7.6,3.4));lab=['种子1','种子2','种子3','种子4']
axs[0].bar(lab,[S[k]['phi'] for k in seeds],color='#4a5568');axs[0].axhline(2/3,color='r',ls='--',lw=1);axs[0].set_ylim(0,1);axs[0].set_title('格局占比 φ（红线 2/3＝“格局主导”判据）',fontsize=9)
axs[1].bar(lab,[S[k]['C'] for k in seeds],color='#2f855a');axs[1].set_title('疏密对比 C（疏处残差均值 − 密处残差均值）',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'figs/fig4_phi_C.png',dpi=150);plt.close()
# fig5 knobs
items=[('T5','地面对数律\n壁模型'),('T6','同上，粗糙度\n取外推值'),('T7','入口缓冲带\n缩短'),('T9b','平直立面\n自由滑移')]
key={'T5':'T5_on','T6':'T6_on','T7':'T7','T9b':'T9b_on'}
fig,ax=plt.subplots(figsize=(7.4,3.8));xs=[];dv={}
for j,(t,nm) in enumerate(items):
  for s,off in ((101,-0.12),(102,0.12)):
    dd=S[f'{key[t]}_s{s}']['MSE_pat']-S[f'off_s{s}']['MSE_pat'];dv[f'{t}_s{s}']=dd
    ax.bar(j+off,dd,width=0.22,color='#3182ce' if s==101 else '#90cdf4',label=('种子 2' if s==101 else '种子 3') if j==0 else None)
dfine=S['fine_0p5']['MSE_pat']-S['off_s100']['MSE_pat'];dv['fine_0p5']=dfine
ax.bar(len(items),dfine,width=0.3,color='#dd6b20',label='0.5 m 全域加密（种子 1，多因素同时变）')
ax.axhspan(-Rpat,Rpat,color='gray',alpha=0.2,label=f'种子噪声带 ±{Rpat:.4f}')
ax.set_xticks(range(len(items)+1));ax.set_xticklabels([n for _,n in items]+['0.5 m\n加密'],fontsize=8);ax.axhline(0,color='k',lw=0.6)
ax.set_ylabel('格局误差变化 ΔMSE_pat（负＝变好）');ax.legend(fontsize=7,loc='lower left');ax.set_title('各项改动对格局误差的影响（同种子配对）',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'figs/fig5_knobs.png',dpi=150);plt.close()
num['delta_MSE_pat']=dv;num['fine']={x:S['fine_0p5'][x] for x in ('a','MSE_pat','phi','C','MAE')}
num['dense_median']=med
json.dump(num,open(Path(sys.argv[0]).with_name('numbers_wp1.json'),'w'),ensure_ascii=False,indent=1)
print(json.dumps(num,ensure_ascii=False,indent=1))
