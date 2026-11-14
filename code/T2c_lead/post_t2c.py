# T2c：按离半格墙面的真实高度 h 取 Case E 80 点，B2u 1 m 对 T2b 0.5 m，冻结 table() 原样。只读源场。
import sys,json,csv,math,pathlib
import numpy as np
sys.path.insert(0,'/scratch/04448/[用户]/r24_luw/T2b_post'); import post_t2 as m
R='/scratch/04448/[用户]/r24_luw/T2b_post/'
V05=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2b_05m/case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk')
V1=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk')
ref=json.load(open(R+'B2u_reference_points.json'));base=list(csv.DictReader(open(R+'baseline.csv')));wid=list(csv.DictReader(open(R+'widths.csv')))
U=ref['uref'];out={'uref':U}
def first_fluid(v):
    dx=v['spacing'][0];res=[]
    for xy in ((2.,250.),(100.,40.),(480.,250.),(250.,480.),(480.,480.)):
        i=round(xy[0]/dx);j=round(xy[1]/dx);col=[float(v['fields']['fluid'][k,j,i])>.5 for k in range(0,int(25/dx))]
        k0=col.index(True);res.append({'xy':xy,'first_fluid_k':k0,'label_z':-20+k0*dx,'below_all_solid':not any(col[:k0])})
    ks={r['first_fluid_k'] for r in res};assert len(ks)==1,res
    k0=ks.pop();return res,-20+(k0-.5)*dx   # 半格墙面标签
v1=m.vtk_open(V1);v05=m.vtk_open(V05)
ff1,w1=first_fluid(v1);ff05,w05=first_fluid(v05);out['first_fluid']={'1m':ff1,'05m':ff05,'wall_label_1m':w1,'wall_label_05m':w05}
# 1 m 水平映射：哪一个复现 baseline.csv（标签 2.0）
bmap={int(r['id']):float(r['Su']) for r in base};rep={}
for sh in ((0.,0.),(1.,1.)):
    d=[abs(m.point_sample(v1,p,(sh[0],sh[1],0.))['Su']/U-bmap[p['id']]) for p in ref['rows']];rep[str(sh)]=max(d)
out['b2u_reproduction_maxabs']=rep;sh1=min(rep,key=rep.get);sh1=eval(sh1);out["b2u_reproduction_ok"]=rep[str(sh1)]<1e-5
def rows(v,sh):return [{'id':p['id'],'obs':p['after'],'Su_ratio':(s:=m.point_sample(v,p,sh))['Su']/U,'fluid_corners':s['fluid_corners'],'solid_weight':s['solid_weight']} for p in ref['rows']]
def mae(rs):return sum(abs(r['Su_ratio']-r['obs']) for r in rs)/len(rs)
out['by_h']={}
for h in (1.5,2.0,2.5):
    z1=w1+h-2.;z05=w05+h-2.   # point_sample 取标签 2+shift_z
    r1=rows(v1,(sh1[0],sh1[1],z1));b=[{'id':str(r['id']),'obs':str(r['obs']),'Su':str(r['Su_ratio'])} for r in r1]
    e={'label_1m':2+z1,'label_05m':2+z05,'B2u_MAE':mae(r1),'B2u_ratio_total':sum(r['Su_ratio'] for r in r1)/sum(r['obs'] for r in r1),'B2u_solid_points':[r['id'] for r in r1 if r['fluid_corners']<8],'tables':{}}
    for nm,sh in (('primary_05_05',(.5,.5,z05)),('control_1_1',(1.,1.,z05))):
        e['tables'][nm]=m.table(rows(v05,sh),b,wid)
    out['by_h'][str(h)]=e
json.dump(out,open('result_t2c.json','w'),indent=1)
print('T2C_DONE',json.dumps({h:{'B2u_MAE':e['B2u_MAE'],**{k:(t['groups']['>=15']['delta_r'],t['all_gates_pass']) for k,t in e['tables'].items()}} for h,e in out['by_h'].items()}),flush=True)
