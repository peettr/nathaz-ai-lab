"""L26.23 R1 判读 v2 描述性数字（不进判定）。用法: python3 本脚本 S2_per_tap_main.csv R1_per_tap_main.csv"""
import csv,sys,json,numpy as np
def rd(p): return {int(r['tap_id']):r for r in csv.DictReader(open(p))}
a,b=rd(sys.argv[1]),rd(sys.argv[2]); out={}
for zone in ['side_separated','side_corner','side_leading','windward','windward_corner','leeward']:
  ids=sorted(i for i in a if a[i]['zone']==zone); assert all(b[i]['zone']==zone for i in ids)
  z={'N':len(ids)}
  for P in ['50','90']:
    f=lambda r,k: float(r[f'neg_{P}_{k}'])
    D=np.array([f(b[i],'LES')-f(a[i],'LES') for i in ids])
    rng=np.random.default_rng(4101009); bs=[np.median(rng.choice(D,len(D))) for _ in range(2000)]
    lo,hi=np.quantile(bs,[.05,.95])
    hS=np.median([f(a[i],'halfA_LES')-f(a[i],'halfB_LES') for i in ids]); hR=np.median([f(b[i],'halfA_LES')-f(b[i],'halfB_LES') for i in ids])
    dT=lambda r:[f(r[i],'LES')-f(r[i],'TPU') for i in ids]
    e=lambda r:[abs(f(r[i],'LES')-f(r[i],'TPU'))/abs(f(r[i],'TPU')) for i in ids if abs(f(r[i],'TPU'))>=0.05]
    z['P'+P]=dict(medD=float(np.median(D)),CI90=[float(lo),float(hi)],D_pos=int((D>0).sum()),absD_gt_0p10=int((abs(D)>.10).sum()),absD_gt_0p20=int((abs(D)>.20).sum()),
      halfAminusB_signed_median_S2=float(hS),halfAminusB_signed_median_R1=float(hR),
      dCp_vs_TPU_median_S2=float(np.median(dT(a))),dCp_vs_TPU_median_R1=float(np.median(dT(b))),
      e_median_S2=float(np.median(e(a))),e_median_R1=float(np.median(e(b))))
  out[zone]=z
print(json.dumps(out,ensure_ascii=False,indent=1))
