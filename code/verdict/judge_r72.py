"""R72 判读：实验卡⑤（10-21 09:45 写定）+ 04_Decisions/K_判据配对与72h步长_20261015.md（10-22 补充：72 h 正式 dt12，G72/P72 dt15 作附列）
+ 口径 v2（04_Decisions/K_观测口径_最小面积与时间窗_20261015.md：左删失 t≤00Z、右删失 t>09Z 按区间代入，所有取值一致才判；
时间不可判不得计"不差于"正票，只有位置或存在性已单独不满足才计"非不差于"）。只读 CSV。用法：python3 -I judge_r72.py out.json"""
import csv, sys, json
from datetime import datetime, timezone
B='./16_PETW/02_Subprojects/WRF_Modeling/07_Validation/lab_K_akron/'
NEW=B+'R13_v1/R72_readout/verified_1617717/results/'   # dt12：R72/G72/P72
OLD=B+'R13_v1/R72_readout/verified_1617717/frozen/'                                 # dt15：G72/P72（冻结）
W0=datetime(2020,6,9,0,0,tzinfo=timezone.utc); WEND=540.0
def rows(p): return list(csv.DictReader(open(p)))
def load(d,dt):
    tab,ex={},{}
    for tier,f in (('64','PAIR72_FORMAL_V2.csv'),('16','PAIR72_SENSITIVITY16_V2.csv')):
        for r in rows(d+f): tab[(r['member']+dt,tier)]=r
    for r in rows(d+'PAIR72_EXIST150_V2.csv'): ex[(r['member']+(dt if r['member']!='OBS' else ''),r['tier'])]=r['exists_within_150km_03_09Z']=='True'
    return tab,ex
t15,e15=load(NEW,'_dt12'); t20,e20=load(OLD,'_dt15'); tab={**t15,**t20}; ex={**e15,**e20}
def mins(s): return (datetime.fromisoformat(s)-W0).total_seconds()/60
def t_interval(r):
    if r['model_left_censored']=='True': return (-1e9,0.0),'左删失 t≤00Z'
    if not r['model_first50_utc']: return (WEND+1e-6,1e9),'右删失 t>09Z（窗内未首现）'
    t=mins(r['model_first50_utc']); return (t,t),'%.0f min'%t
def absr(iv,o):
    lo,hi=iv; v=[abs(lo-o),abs(hi-o)]
    return (0.0 if lo<=o<=hi else min(v), max(v))
def nw(X,Y,tier):
    rx,ry=tab[(X,tier)],tab[(Y,tier)]
    o=mins(rx['obs_first50_utc']); assert abs(o-mins(ry['obs_first50_utc']))<1e-9 and rx['obs_left_censored']!='True'
    px,py=float(rx['centroid_distance_km']),float(ry['centroid_distance_km']); pos=px<=py+50
    ivx,dx=t_interval(rx); ivy,dy=t_interval(ry); ax,ay=absr(ivx,o),absr(ivy,o)
    tim=True if ax[1]<=ay[0]+60 else (False if ax[0]>ay[1]+60 else None)
    exi=not(ex[(Y,tier)] and not ex[(X,tier)])
    v=False if (not pos or not exi) else tim
    f=lambda a:'%.0f'%a if a<1e8 else '∞'
    return dict(X=X,Y=Y,tier=tier,
      pos='%.1f ≤ %.1f + 50 = %.1f → %s'%(px,py,py+50,pos),
      time='tobs=%.0f；X:%s → |tX−tobs|∈[%s,%s]；Y:%s → |tY−tobs|+60∈[%s,%s] → %s'%(o,dx,f(ax[0]),f(ax[1]),dy,f(ay[0]+60),f(ay[1]+60),{True:'满足',False:'不满足',None:'不可判'}[tim]),
      exist='Y 150km 内=%s，X=%s → %s'%(ex[(Y,tier)],ex[(X,tier)],exi),
      verdict={True:'不差于',False:'非不差于',None:'时间不可判·不计票'}[v],raw=v)
def combine(rs):
    vs=[r['raw'] for r in rs]
    if None in vs: return '不判（时间不可判）' if all(r['raw'] is None or r['raw'] is False for r in rs) and not all(v is False for v in vs) else '不判'
    if len(set(vs))==1: return '不差于' if vs[0] else '非不差于'
    return '面积敏感·不判'
out=[]
for lab,X,Y,X2,Y2 in [('(a) 层数：R72 不差于 G72','R72_dt12','G72_dt12','R72_dt12','G72_dt15'),
                      ('(b) 模型：P72 不差于 R72','P72_dt12','R72_dt12','P72_dt15','R72_dt12')]:
    formal=[nw(X,Y,t) for t in ('64','16')]; app=[nw(X2,Y2,t) for t in ('64','16')]
    cf,ca=combine(formal),combine(app)
    final=cf if cf==ca else ('步长敏感·不判' if '不判' not in cf+ca else cf)
    out.append(dict(label=lab,formal=formal,formal_combined=cf,appendix=app,appendix_combined=ca,final=final))
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False,indent=1)
for o in out:
    print(o['label'],'→ 正式',o['formal_combined'],'| 附列',o['appendix_combined'],'| 最终',o['final'])
    for k in ('formal','appendix'):
        for r in o[k]: print('  [%s %s vs %s 档%s] 位置 %s；时间 %s；存在 %s ⇒ %s'%(k,r['X'],r['Y'],r['tier'],r['pos'],r['time'],r['exist'],r['verdict']))
