"""L22.10 M1-2 事后补判（看过数据后加，标"事后"）：WOW 谱有固定频率尖峰（47、93.75、187.5、230 Hz，风机/电气），
预定判据的 f_ok 被尖峰顶高。补判：谱先做 41 点（5.0 Hz）滑动中位数去尖峰，噪声底仍取 200–250 Hz 中位，f_ok = 平滑谱 ≥10×底 的最高频率。
约化频率 nH/U = f×H_m/U_m，H_m=0.734 m（2022_ACWE Fig.2 推得），U_m=18.72 m/s（风速文件，40% 风机档）。"""
import sys,glob,os,json,numpy as np
from scipy.ndimage import median_filter
D=sys.argv[1]; H,U=0.734,18.72; out={}
for f in sorted(glob.glob(D+'/*_spec.npy')):
    fr,Pm,Pa=np.load(f); k=os.path.basename(f).replace('_spec.npy','')
    r={}
    for nm,S in [('tap_median',Pm),('all_mean',Pa)]:
        Ss=median_filter(S,41,mode='nearest'); w=(fr>=200)&(fr<=250); fl=np.median(Ss[w])
        ok=(Ss>=10*fl)&(fr>0.5); fo=float(fr[ok].max())
        r[nm]=dict(f_ok_smooth_Hz=fo,nHU=round(fo*H/U,3))
    out[k]=r
json.dump(out,open(D+'/m1_bw_prj5592_post.json','w'),indent=1)
for k,v in out.items(): print(k[16:42],v['tap_median']['f_ok_smooth_Hz'],v['tap_median']['nHU'],v['all_mean']['f_ok_smooth_Hz'],v['all_mean']['nHU'])
