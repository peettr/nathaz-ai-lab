# 事后诊断（11-01，看过留出之后写，不改判定）：通带里有多少是全表面共模，失败是否来自共模
import numpy as np,json,sys
T=sys.argv[1]; L=sys.argv[2]
def ld(n):
    z=np.load(f'{T}/{n}.npz'); t=z['t']; k=(t>=float(z['keep']))&(np.arange(len(t))>=100); return t[k],z['cp'][k].astype('f4')
def corr(a,b): a=a-a.mean(0);b=b-b.mean(0);return (a*b).sum(0)/np.sqrt((a*a).sum(0)*(b*b).sum(0)+1e-20)
def stats(y,o):
    d={}
    f=lambda x:x-x.mean(0)
    cy=f(y).mean(1,keepdims=True); co=f(o).mean(1,keepdims=True)
    d['raw_corr']=float(corr(o,y).mean()); d['raw_rmse']=float(np.sqrt(((o-y)**2).mean(0)).mean())
    d['nocm_corr']=float(corr(f(o)-co,f(y)-cy).mean()); d['nocm_rmse']=float(np.sqrt(((f(o)-co-(f(y)-cy))**2).mean(0)).mean())
    d['cm_corr']=float(corr(co,cy)[0]); return d
_,y=ld('A1_101');_,c=ld('A1_202');t7,v7=ld('v7');_,d1=ld('P101_drive')
R={}
fy=y-y.mean(0); cm=fy.mean(1,keepdims=True); R['test_cm_var_fraction_surface']=float((cm**2).mean()/(fy**2).mean())
tv=v7-v7.mean(0); cmv=tv.mean(1,keepdims=True); R['v7_cm_var_fraction_surface']=float((cmv**2).mean()/(tv**2).mean())
R['ceiling_A1_202_vs_A1_101_surface']=stats(y,c)
i=(t7>=360); R['train_same_inflow_P101_drive_vs_v7']=stats(v7[i][:len(d1)],d1[:i.sum()])
Z=np.load(f'{L}/out/preds_taps.npz'); yt=Z['y']
R['taps']={}
for k in ('transolver','fno','ridge','qs0','qslag'): R['taps'][k]=stats(yt,Z[k])
ceil=np.load(f'{T}/A1_202.npz'); t_=ceil['t']; kk=t_>=360; ctap=ceil['cp'][kk][:len(yt),8000:].astype('f4'); R['taps']['ceiling_A1_202']=stats(yt,ctap)
# 分面：40 测点里 V 系列迎风/背风、H 系列
names=list(np.load(f'{T}/A1_101.npz')['tap_cols']); ww=[i for i,n in enumerate(names)][:8]
for k in ('qs0','ridge','transolver'): R['taps'][k+'_per_tap_corr_first16']=[round(float(x),2) for x in corr(Z[k],yt)[:16]]
# 谱：全表面平均功率按频带
Y=np.abs(np.fft.rfft(fy,axis=0))**2; f=np.fft.rfftfreq(len(fy),.2); P=Y.mean(1)
R['test_band_power_fraction']={f'{a}-{b}':float(P[(f>=a)&(f<b)].sum()/P.sum()) for a,b in ((0,.1),(.1,.3),(.3,.6),(.6,1.1))}
Yc=np.abs(np.fft.rfft(cm[:,0]))**2; R['test_cm_band_fraction']={f'{a}-{b}':float(Yc[(f>=a)&(f<b)].sum()/Yc.sum()) for a,b in ((0,.1),(.1,.3),(.3,.6),(.6,1.1))}
json.dump(R,open(f'{L}/out/diag_posthoc.json','w'),indent=1,ensure_ascii=False); print(json.dumps(R,indent=0,ensure_ascii=False))
