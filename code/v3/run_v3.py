#!/usr/bin/env python3
"""A2 v3: acceleration-cost LQ preview, validation gate, then held-out test. CPU only."""
import sys, json, time, hashlib, argparse
from pathlib import Path
import numpy as np
import scipy.linalg as la
from scipy.signal import welch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_a2 as old
DT=.1; LEADS=(0,.5,1,2,3,5,8)

def plant(freq,stroke_weight,effort):
    m=.05; wr=2*np.pi*freq; k=wr**2; c=.04*wr
    A=np.array([[0,1,0,0],[-k,-c,0,0],[0,0,0,1],[k,c,0,0]],float)
    B=np.array([[0],[-1],[0],[1+1/m]]); E=np.array([[0],[1],[0],[-1]])
    aug=np.zeros((6,6));aug[:4,:4]=A;aug[:4,4:5]=B;aug[:4,5:6]=E
    exp=la.expm(aug*DT); Ad=exp[:4,:4]; Bd=exp[:4,4:5]; Ed=exp[:4,5:6]
    C=np.array([[-k,-c,0,0]],float); D=np.array([[-1.]])
    # stage cost: a_k^2 + eta*r_k^2 + epsilon*u_k^2 + small regularization
    Q=C.T@C+np.diag([1e-5,1e-5,stroke_weight,1e-5]); N=C.T@D; R=D.T@D+effort
    P=la.solve_discrete_are(Ad,Bd,Q,R,s=N)
    H=R+Bd.T@P@Bd; K=la.solve(H,Bd.T@P@Ad+N.T); Acl=Ad-Bd@K
    # Bellman disturbance linear term s_k = g*d_k + Acl.T*s_{k+1}.
    # Direct acceleration output contributes D.T*d_k; it was missing in v2.
    g=[邮箱]+Acl.T@P@Ed
    kern=np.zeros(81);kern[0]=((Bd.T@P@Ed+D.T)/H)[0,0]
    vec=g.copy()
    for j in range(1,81):
        kern[j]=((Bd.T@vec)/H)[0,0];vec=Acl.T@vec
    return Ad,Bd[:,0],Ed[:,0],K[0],kern,k,c

def simulate(F,preview,plant,limit=np.inf,umax=np.inf,detail=False):
    Ad,B,E,K,kern,k,c=plant; n=len(F); state=np.zeros(4); us=np.zeros(n); acc=np.zeros(n); strokes=np.zeros(n); hits=0;clips=0
    for i in range(n):
        u=-float(K@state)-float(kern[:preview.shape[1]]@preview[i])
        if abs(u)>umax: clips+=1;u=float(np.clip(u,-umax,umax))
        a=F[i]-k*state[0]-c*state[1]-u
        nxt=Ad@state+B*u+E*F[i]
        if abs(nxt[2])>limit:
            hits+=1;nxt[2]=np.sign(nxt[2])*limit
            if nxt[2]*nxt[3]>0:
                # inelastic stop, relative momentum transferred to structure
                impulse=.05/1.05*nxt[3]/DT;nxt[1]+=impulse*DT;nxt[3]=0;a+=impulse
        acc[i]=a;us[i]=u;strokes[i]=abs(nxt[2]);state=nxt
    rms=lambda z:float(np.sqrt(np.mean(z*z)))
    ans={'acc_rms':rms(acc),'acc_peak':float(np.max(abs(acc))),'stroke_peak':float(max(strokes)),'stroke_rms':rms(strokes),'u_rms':rms(us),'u_peak':float(np.max(abs(us))),'hit_fraction':hits/n,'clip_fraction':clips/n}
    return (ans,us,acc) if detail else ans

def target_indices(t,start,end):
    # Complete 8s lookahead for every issue and identical denominator/window.
    return np.flatnonzero((t>=start)&(t<end))[::5]

def oracle(F,inds):return np.stack([F[inds+5*j] for j in range(81)],axis=1)
def blanks(n):return np.zeros((n,1))

def predictors(x,y,t,w,mu,inds):
    # v2 predictor, refit without modifying its files. Validation and test issue forecasts.
    tr=np.arange(300,len(t));tr=tr[(t[tr]<462)&(tr%5==0)]
    va=np.arange(300,len(t));va=va[(t[va]>=462)&(t[va]<522)&(va%5==0)]
    _,_,vt=np.linalg.svd(((x[tr]-x[tr].mean(0))/np.maximum(x[tr].std(0),1e-8)).astype('float32'),full_matrices=False)
    xm=x[tr].mean(0);xs=np.maximum(x[tr].std(0),1e-8)
    z=((x-xm)/xs).astype('float32')@vt[:9].T
    design=lambda ii:np.concatenate([z[ii-l] for l in old.LAGS],axis=1).astype('float64')
    A=design(tr); V=design(va); E=design(inds); am=A.mean(0);ast=np.maximum(A.std(0),1e-8)
    A=(A-am)/ast;V=(V-am)/ast;E=(E-am)/ast
    G=A.T@A;eye=np.eye(G.shape[0]); fitted={}; skill={}
    for h in LEADS:
        shift=round(old.FS*h); Y=y[tr+shift];Yv=y[va+shift];ym=Y.mean(0)
        rhs=A.T@(Y-ym)
        choices=[]
        for alpha in (100.,1000.,10000.):
            coef=la.solve(G+alpha*eye,rhs,assume_a='pos',check_finite=False)
            choices.append((np.mean((V@coef+ym-Yv)**2),alpha,coef))
        _,alpha,coef=min(choices,key=lambda v:v[0]);pv=(V@coef+ym)@w-mu
        # validation target-aligned quality; use nonnegative r² as reliability factor
        tv=y[va+shift]@w-mu
        correlation=float(np.corrcoef(pv,tv)[0,1]) if np.std(pv)>1e-12 else 0.
        fitted[h]=(E@coef+ym)@w-mu
        skill[h]={'validation_force_r':correlation,'r2_discount':float(max(0,correlation)**2),'ridge_alpha':alpha}
    return fitted,skill

def preview_matrix(signals,inds,h,discount):
    n=int(round(h/DT))+1
    src=np.stack([signals[k] for k in LEADS],axis=1)
    mat=np.array([np.interp(np.arange(n)*DT,LEADS,src[i]) for i in range(len(inds))])
    # validation-only reliability per lead, interpolated on the same horizon grid
    factors=np.interp(np.arange(n)*DT,LEADS,[discount[k] for k in LEADS])
    return mat*factors

def main():
    pa=argparse.ArgumentParser();pa.add_argument('--input',type=Path,required=True);pa.add_argument('--out',type=Path,required=True);a=pa.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    for f in ['results.md','params.md','metrics.json','control.png']:
        if (a.out/f).exists():raise FileExistsError(f)
    tick=time.monotonic()
    hashes=json.loads((Path(__file__).resolve().parents[2]/'lbm_transfer/provenance.json').read_text())
    for name,meta in hashes.items():
        got=hashlib.sha256((a.input/name).read_bytes()).hexdigest()
        if got!=meta['sha256']:raise ValueError('source hash mismatch '+name)
    t,x,y,q=old.load(a.input);w,_,_,_=old.weights();F=y@w; mu=float(np.mean(F[t<462])); F-=mu
    val=target_indices(t,462,514);test=target_indices(t,522,634)
    assert t[val[-1]+400]<=522 and t[test[-1]+400]<=642
    f,ps=welch(F[t<462],50,nperseg=4096);mask=(f>.08)&(f<1.2)
    freq={'near_spectral_peak':float(f[mask][np.argmax(ps[mask])]),'off_resonance':1.4}
    # Explicit, bounded validation-only candidate grid. Do not tune to test response.
    choices=[(eta,eps) for eta in (0.0001,.01,1.) for eps in (.0001,.01,.1)]
    selected={};gate={};vforce=F[val];tforce=F[test]
    for label,fr in freq.items():
        ranked=[]
        for eta,eps in choices:
            model=plant(fr,eta,eps);fb=simulate(vforce,blanks(len(val)),model)
            perfect=simulate(vforce,oracle(F,val),model)
            reduction=1-perfect['acc_rms']/fb['acc_rms']
            ranked.append((reduction,eta,eps,fb,perfect))
        # Prefer smallest validation improvement meeting gate; protects against cherry-picked huge actuation.
        passing=sorted((r for r in ranked if r[0]>=.3),key=lambda r:(r[4]['u_rms'],r[4]['stroke_peak']))
        if passing: r=passing[0];selected[label]=(r[1],r[2])
        gate[label]=[{'reduction':float(r[0]),'stroke_peak':r[4]['stroke_peak'],'u_rms':r[4]['u_rms'],'eta':r[1],'eps':r[2]} for r in ranked]
        print('gate',label,'best',max(z[0] for z in ranked),'selected',selected.get(label),flush=True)
    if not selected:
        report='控制模型自检未过：验证集两档频率中，完美8秒预视均未达到≥30%；按任务书停止第二步。候选与原因见 metrics.json。\n'
        payload={'status':'gate_failed','gate':gate,'frequencies_Hz':freq}
        (a.out/'metrics.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
        (a.out/'results.md').write_text(report)
        (a.out/'params.md').write_text('未进第二步；模型参数与网格见 run_v3.py。\n')
        print(report,flush=True);return
    if len(selected)!=2:
        print('Only one frequency passed; second still reported as gated out.',flush=True)
    results={}; predicted={}; diagnostics={}
    for station,velocity in x.items():
        predicted[station]={};diagnostics[station]={}
        for target,yy in [('raw',y),('acoustic_notch',old.filtered(y))]:
            pred,sk=predictors(velocity,yy,t,w,mu,test)
            predicted[station][target]=pred;diagnostics[station][target]=sk
        print('predictor',station,flush=True)
    umax=20*float(np.std(F[t<462])) # high force cap; actual clip fractions reported
    for label,fr in freq.items():
        if label not in selected:continue
        eta,eps=selected[label];mod=plant(fr,eta,eps)
        fb_free=simulate(tforce,blanks(len(test)),mod)
        limits={'unlimited':None,'loose':1.5*fb_free['stroke_peak'],'tight':.75*fb_free['stroke_peak']}
        results[label]={}
        for lname,lim in limits.items():
            actual_lim=np.inf if lim is None else lim
            fb=simulate(tforce,blanks(len(test)),mod,actual_lim,umax)
            truth=simulate(tforce,oracle(F,test),mod,actual_lim,umax)
            gain=fb['acc_rms']-truth['acc_rms']
            node={'limit':lim,'feedback':fb,'perfect_8s':truth,'perfect_reduction':float(gain/fb['acc_rms']),'predicted':{}}
            for station in old.STATIONS:
                node['predicted'][station]={}
                for target in ('raw','acoustic_notch'):
                    node['predicted'][station][target]={}
                    discount={h:diagnostics[station][target][h]['r2_discount'] for h in LEADS}
                    for h in (.5,1,2,3,5):
                        pv=preview_matrix(predicted[station][target],test,h,discount)
                        met=simulate(tforce,pv,mod,actual_lim,umax)
                        benefit=fb['acc_rms']-met['acc_rms']
                        met.update({'benefit_fraction_of_perfect':float(benefit/gain) if gain>1e-12 else None,'reduction':float(benefit/fb['acc_rms']),'useful':bool(benefit/fb['acc_rms']>=.1 and met['stroke_peak']<=fb['stroke_peak']+1e-9)})
                        node['predicted'][station][target][str(h)]=met
            results[label][lname]=node
            print('case',label,lname,'fb',fb['acc_rms'],'perfect',truth['acc_rms'],'gain',node['perfect_reduction'],'limit',lim,flush=True)
    payload={'status':'completed','data':'single-realization Silsoe v7 LBM, hashed CSV read-only','split_s':{'train':[48,462],'validation_issue':[462,514],'test_issue':[522,634],'max_lead':8},'q':q,'weights':dict(zip(old.TAPS,map(float,w))),'freq_Hz':freq,'gate_candidates_validation':gate,'selected':selected,'force_cap_20_train_sigma':umax,'test':results,'validation_force_skill':diagnostics,'distances_m':old.DIST,'runtime_s':time.monotonic()-tick}
    (a.out/'metrics.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(2,3,figsize=(16,8),layout='constrained')
    for row,label in enumerate(freq):
        if label not in results:continue
        for col,lname in enumerate(('unlimited','loose','tight')):
            ax=axes[row,col];node=results[label][lname]
            for s in old.STATIONS:
                vals=[node['predicted'][s]['raw'][str(h)]['benefit_fraction_of_perfect'] for h in (.5,1,2,3,5)]
                ax.plot((.5,1,2,3,5),vals,marker='o',label=f'{s} ({old.DIST[s]:g}m)')
            ax.axhline(0,color='black',lw=.6);ax.axhline(1,color='black',ls='--',lw=.6)
            ax.set(title=f'{label} / {lname} (perfect gain {node["perfect_reduction"]:.1%})',xlabel='lead (s)',ylabel='predicted benefit / perfect benefit');ax.grid(alpha=.2)
            if row==0 and col==0:ax.legend(fontsize=7)
    fig.savefig(a.out/'control.png',dpi=130);plt.close(fig)
    lines=['# A2 v3 预视控制自检与测试','',f'原始单次 LBM，SHA256 全部与 lbm_transfer/provenance.json 匹配；工作站 CPU，0 CU；运行 {payload["runtime_s"]:.1f}s。v2 未改。','', '预测输入仅速度，面积权重和训练期恒定 q 沿用 v2；陷波仅离线对照。验证段选控制候选与 r² 折扣，测试段不调。', '','## 自检','']
    for label in freq:
        best=max(gate[label],key=lambda z:z['reduction'])
        lines.append(f'{label}: 验证最佳真值8s增益 {best["reduction"]:.2%}；选用 {selected.get(label)}。')
    lines+=['','## 测试对照','频率 / 行程 | FB a_RMS | 真值 a_RMS | 真值收益 | 限位 | 真值行程峰值 | 最佳预测（原始目标；站/τ/收益比例/降幅/行程） | 过联合闸门数','---|---:|---:|---:|---:|---:|---|---:']
    for label in results:
        for lname,node in results[label].items():
            allv=[(s,h,v) for s in old.STATIONS for h,v in node['predicted'][s]['raw'].items()]
            valid=[z for z in allv if z[2]['benefit_fraction_of_perfect'] is not None]
            best=max(valid,key=lambda z:z[2]['benefit_fraction_of_perfect']) if valid else None
            desc=f'{best[0]}/{best[1]}s/{best[2]["benefit_fraction_of_perfect"]:.2f}/{best[2]["reduction"]:.1%}/{best[2]["stroke_peak"]:.4g}' if best else '不可定义（真值无正收益）'
            passes=sum(v['useful'] for _,_,v in allv)
            lines.append(f'{label}/{lname} | {node["feedback"]["acc_rms"]:.5f} | {node["perfect_8s"]["acc_rms"]:.5f} | {node["perfect_reduction"]:.2%} | {node["limit"] if node["limit"] is not None else "∞"} | {node["perfect_8s"]["stroke_peak"]:.4g} | {desc} | {passes}')
    lines+=['','收益比例=(FB a_RMS−预测 a_RMS)/(FB a_RMS−真值 a_RMS)。当真值收益≤0时比例记 null，不把它叫性能上界；固定 LQ 律真值8秒仅是完美信号参照。完整的六站×五提前量×两目标×两频×三行程、撞限及力裁剪率见 metrics.json。','','闸门：预测相对同档纯反馈 a_RMS 至少降低10% 且行程峰值不增大（数值比较容差 1e−9）。预视相关不等于控制效益；这只是迎风面 Cp 代理荷载/无量纲 AMD，不能外推到建筑。']
    (a.out/'results.md').write_text('\n'.join(lines)+'\n')
    (a.out/'params.md').write_text('# A2 v3 参数与来源\n\n数据、恒定 q、速度输入、11 点面权重、离线陷波：沿用 v2 params.md 与 run_a2.py；原 CSV SHA256 对照本线 lbm_transfer/provenance.json。\n\n假设：M=1，m=.05，ζ=.02，频率近训练谱峰和1.4 Hz，控制步长0.1 s；单位为代理无量纲，不是实际楼体。\n\n新控制假设：每步 a²+ηr²+εu²，Q=CᵀC+diag(1e−5,1e−5,η,1e−5)，N=CᵀD，R=DᵀD+ε，a=Cx+Du+F，C=[−k,−c,0,0]，D=−1。Bellman 线性扰动项包括同一步 DᵀF；用离散 DARE 求 P，H=R+BᵀPB，K=H⁻¹(BᵀPA+Nᵀ)，g=Cᵀ−KᵀDᵀ+(A−BK)ᵀPE，核 h₀=H⁻¹(BᵀPE+Dᵀ)，hⱼ=H⁻¹Bᵀ[(A−BK)ᵀ]ʲ⁻¹g。式子来自本脚本二次型 Bellman 推导，无文献背书；此前 v2 的状态权重和前馈遗漏加速度同一步项，不可直接对比其数值。\n\nη/ε 网格分别 (0.0001,.01,1.) / (.0001,.01,.1)，验证窗挑达30%者中力RMS最小的组合；测试不重调。力上限=20×训练风力标准差，未限位自检使用∞；三行程为∞、无约束FB峰值×1.5、×.75。所有限位方案同一反馈/前馈增益；非弹性止挡动量回传与冲量加速度沿用 v2，属于简化假设。折扣=max(0,验证 Pearson r)²，对各提前量插值；对比原始目标与离线声学陷波目标（不声称可在线）。各候选、峰值、裁剪比例和验证技巧见 metrics.json。\n')
    print('DONE',payload['runtime_s'],flush=True)
if __name__=='__main__':main()
