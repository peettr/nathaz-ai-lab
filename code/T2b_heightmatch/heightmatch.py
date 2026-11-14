# 同离地高度诊断：0.5 m 场取 VTK 标签 z=1.5（= 真实离地约 1.0 m，与 1 m 场标签 z=2.0 同真实高度），按冻结 table() 打分。
# 依据：setup.cpp:4110 把 STL 最低点平移到格点 1，VTK 原点 z=-20 → 标签高度比真实高度高 1 个 dx（Case A 屋顶掩膜已证 z 偏 +1 格）。
import json,csv,math,sys
import numpy as np
sys.path.insert(0,'/scratch/04448/[用户]/r24_luw/T2b_post')
import post_t2 as m
R='/scratch/04448/[用户]/r24_luw/T2b_post/'
ref=json.load(open(R+'B2u_reference_points.json'))
base=list(csv.DictReader(open(R+'baseline.csv')));wid=list(csv.DictReader(open(R+'widths.csv')))
dx=.5;nx=ny=1000;ox=oy=0.
out={}
for zl in ('1.5','2'):
    su=np.fromfile(R+f'plane_z{zl}_Su.f32le','<f4').reshape(ny,nx);fl=np.fromfile(R+f'plane_z{zl}_fluid.f32le','<f4').reshape(ny,nx)
    for sh in ((.5,.5),(1.,1.)):
        rows=[]
        for p in ref['rows']:
            x=p['xls_xy'][0]+1010.50008-760+sh[0];y=p['xls_xy'][1]+1000.60004-750+sh[1]
            cx,cy=(x-ox)/dx,(y-oy)/dx;i,j=math.floor(cx),math.floor(cy);wx,wy=cx-i,cy-j
            s=0.;c=0;sw=0.
            for dj,di in ((0,0),(0,1),(1,0),(1,1)):
                w=(wx if di else 1-wx)*(wy if dj else 1-wy);s+=w*float(su[j+dj,i+di]);f=fl[j+dj,i+di]>.5;c+=int(f);sw+=w*(not f)
            rows.append({'id':p['id'],'obs':p['after'],'Su_ratio':s/ref['uref'],'fluid_corners':c,'solid_weight':sw})
        t=m.table(rows,base,wid)
        out[f'label_z{zl}_shift{sh}']={'delta_mae':t['delta_mae'],'wide_dr':t['groups']['>=15']['delta_r'],'wide_ratio':[t['groups']['>=15']['ratio_total_1'],t['groups']['>=15']['ratio_total_05']],'wide_improved':t['groups']['>=15']['improved'],'narrow_D':t['groups']['<4'].get('D'),'narrow_impr':t['groups']['<4']['improved'],'near_impr':t['near_group']['improved'],'near_dr':t['near_group']['delta_r'],'near_ratio':[t['near_group']['ratio_total_1'],t['near_group']['ratio_total_05']],'total_ratio':[t['total']['ratio_total_1'],t['total']['ratio_total_05']],'gates':t['gates'],'all':t['all_gates_pass']}
json.dump(out,open('heightmatch.json','w'),indent=1);print(json.dumps(out,indent=1))
