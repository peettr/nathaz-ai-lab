"""R24 判读：按实验卡⑤（10-21 09:45 写定）对 (a) R vs G、(b) P vs R 计算"不差于"。只读 CSV。"""
import csv, sys, json
from datetime import datetime, timezone
B='./16_PETW/02_Subprojects/WRF_Modeling/07_Validation/lab_K_akron/'
def rows(p): return list(csv.DictReader(open(p)))
def T(s): return datetime.fromisoformat(s) if s else None
W0=datetime(2020,6,9,0,0,tzinfo=timezone.utc); W1=datetime(2020,6,9,9,0,tzinfo=timezone.utc)
tab={}
for tier,pf,rf in [('64','PAIR24_v2_final/PAIR24_FORMAL_V2.csv','R13_v1/R24_readout/R24_FORMAL_V2.csv'),
                   ('16','PAIR24_v2_final/PAIR24_SENSITIVITY16_V2.csv','R13_v1/R24_readout/R24_SENSITIVITY16_V2.csv')]:
    for r in rows(B+pf)+rows(B+rf): tab[(r['member'],tier)]=r
ex={}
for p in ['PAIR24_v2_final/PAIR24_EXIST150_V2.csv','R13_v1/R24_readout/R24_EXIST150_V2_full.csv']:
    for r in rows(B+p): ex[(r['member'],r['tier'])]=r['exists_within_150km_03_09Z']=='True'
def t_interval(r):
    """首现时刻区间（分钟，相对 00Z）：左删失 → (-inf,0]；右删失（窗内未首现）→ (540,inf)。"""
    if r['model_left_censored']=='True': return (-1e9,0.0)
    if not r['model_first50_utc']: return (540.0001,1e9)
    t=(T(r['model_first50_utc'])-W0).total_seconds()/60; return (t,t)
def obs_t(r):
    assert r['obs_left_censored']!='True'; return (T(r['obs_first50_utc'])-W0).total_seconds()/60
def abs_range(iv,o):
    lo,hi=iv
    vals=[abs(lo-o),abs(hi-o)]
    mn=0.0 if lo<=o<=hi else min(vals); return (mn,max(vals))
def not_worse(X,Y,tier):
    rx,ry=tab[(X,tier)],tab[(Y,tier)]; o=obs_t(rx); assert abs(o-obs_t(ry))<1e-9
    px,py=float(rx['centroid_distance_km']),float(ry['centroid_distance_km'])
    pos=px<=py+50
    ax,ay=abs_range(t_interval(rx),o),abs_range(t_interval(ry),o)
    # 所有取值都满足 → True；所有取值都不满足 → False；否则不可判
    if ax[1]<=ay[0]+60: tim=True
    elif ax[0]>ay[1]+60: tim=False
    else: tim=None
    exi=not (ex[(Y,tier)] and not ex[(X,tier)])
    if not pos or not exi: v=False
    elif tim is None: v=None
    else: v=tim
    return dict(X=X,Y=Y,tier=tier,pos_X=px,pos_Y_plus50=py+50,pos_ok=pos,t_abs_X=ax,t_abs_Y_plus60=(ay[0]+60,ay[1]+60),time_ok=tim,exist_ok=exi,not_worse=v)
out=[]
for X,Y,lab in [('R24','G24','(a) 层数：R 不差于 G'),('P24','R24','(b) 模型：P 不差于 R')]:
    rs=[not_worse(X,Y,t) for t in ('64','16')]
    vs={r['not_worse'] for r in rs}
    final = rs[0]['not_worse'] if len(vs)==1 and None not in vs else ('面积敏感·不判' if None not in vs else '不可判')
    out.append(dict(label=lab,tiers=rs,final=final))
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False,indent=1,default=str)
for o in out:
    print(o['label'],'→',o['final'])
    for r in o['tiers']: print('  ',r['tier'],'pos',round(r['pos_X'],1),'<=',round(r['pos_Y_plus50'],1),r['pos_ok'],'| t',r['t_abs_X'],'<=',r['t_abs_Y_plus60'],r['time_ok'],'| exist',r['exist_ok'],'=>',r['not_worse'])
