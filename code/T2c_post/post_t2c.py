#!/usr/bin/env python3
"""T2c immutable VTK postprocessing at equal half-way-wall heights."""
import csv, json, math, pathlib, sys, traceback
import numpy as np
import post_t2 as m
R=pathlib.Path(__file__).resolve().parent
V2=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2b_05m/case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk')
V1=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk')
FLAGS=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2b_05m/case_4gpu/RESULTS/native_flags_nearground_z43_45.bin')
H=(1.5,2.,2.5)
SHIFT={'primary':(.5,.5),'control':(1.,1.)}
def main():
    m.ROOT=R
    for p in (V2,V1,FLAGS,R/'post_t2.py',R/'baseline.csv',R/'widths.csv',R/'B2u_reference_points.json'):
        assert p.is_file(),p
    v2,v1=map(m.vtk_open,(V2,V1)); assert v2['dims']==(1000,1000,540) and v2['spacing']==(.5,)*3 and v2['origin']==(0.,0.,-20.)
    assert v1['dims']==(500,500,270) and v1['spacing']==(1.,)*3 and v1['origin']==(0.,0.,-20.)
    ref=json.loads((R/'B2u_reference_points.json').read_text()); points=ref['rows']; assert len(points)==80
    with (R/'baseline.csv').open(newline='') as f: original=list(csv.DictReader(f))
    with (R/'widths.csv').open(newline='') as f: widths=list(csv.DictReader(f))
    assert len(original)==len(widths)==80
    flags=np.memmap(FLAGS,mode='r',dtype='u1',shape=(3,1000,1000))
    # Multiple unobstructed sites; native flags exported at 43..45 are only a cross-check.
    sites=((2.,250.),(100.,40.),(480.,250.))
    levels=[]
    for x,y in sites:
        i,j=round(x/.5),round(y/.5)
        seq=[]
        for k in range(38,47):
            fl=float(v2['fields']['fluid'][k,j,i]); raw=float(v2['fields']['speed_mean'][k,j,i]); assert math.isfinite(fl) and math.isfinite(raw)
            row={'k':k,'z_label_m':v2['origin'][2]+k*.5,'fluid':fl>.5,'Su_raw':raw}
            if 43<=k<=45:
                row['native_flag']=int(flags[k-43,j,i]); row['flag_agrees_vtk']=((row['native_flag']&1)==0)==row['fluid']
                assert row['flag_agrees_vtk'],row
            seq.append(row)
        first=next((q for q in seq if q['fluid']),None)
        assert first is not None and all(not q['fluid'] for q in seq if q['k']<first['k']),(x,y,seq)
        levels.append({'xy_m':[x,y],'first_fluid':first,'levels':seq})
    assert all(a['first_fluid']['k']==41 for a in levels),levels
    wall05=.25; wall1=.5
    out={'sources':[{'path':v['path'],'bytes':v['bytes'],'dims':v['dims'],'origin':v['origin'],'spacing':v['spacing']} for v in (v2,v1)],'uref':ref['uref'],'wall05_label_m':wall05,'wall1_label_m':wall1,'wall_basis':'open-ground first fluid k=41 (0.5m) measured by VTK fluid and native flag overlap; 1m k=21 from prior measured decision; half-link plane half-cell below first fluid center','first_fluid_05':levels,'baseline_label_z2_check':{},'heights':{},'ratio_total_definition':'sum_i(Su_i/Uref) / sum_i(obs_i)','frozen_gates':'DESIGN_T2.md line 17; same-h 1m baseline is recomputed (0.110965 is old label-z2 only); primary/control horizontal shifts fixed before reading metrics'}
    allpoints=[]
    def sample(v,p,xy,label):
        return m.point_sample(v,p,(xy[0],xy[1],label-2.))
    old=[]
    for p in points:
        q=sample(v1,p,(1.,1.),2.)
        b=next(r for r in original if int(r['id'])==int(p['id']))
        d=q['Su']/ref['uref']-float(b['Su']); old.append({'id':p['id'],'Su_ratio':q['Su']/ref['uref'],'baseline_Su':float(b['Su']),'difference':d,'sample':q})
    out['baseline_label_z2_check']={'max_abs_diff':max(abs(x['difference']) for x in old),'mae':sum(abs(x['Su_ratio']-float(next(r for r in original if int(r['id'])==int(x['id']))['obs'])) for x in old)/80,'points':old}
    assert out['baseline_label_z2_check']['max_abs_diff']<1e-8,out['baseline_label_z2_check']['max_abs_diff']
    for h in H:
        label1=wall1+h; label05=wall05+h
        base=[]; samples={name:[] for name in SHIFT}
        for p in points:
            s1=sample(v1,p,(1.,1.),label1); ratio1=s1['Su']/ref['uref']
            base.append({'id':p['id'],'obs':p['after'],'Su':ratio1})
            entry={'id':p['id'],'obs':p['after'],'baseline_1m':s1,'baseline_ratio':ratio1,'fine':{}}
            for name,xy in SHIFT.items():
                s=sample(v2,p,xy,label05);entry['fine'][name]=s
                samples[name].append({'id':p['id'],'obs':p['after'],'Su_ratio':s['Su']/ref['uref'],'fluid_corners':s['fluid_corners'],'solid_weight':s['solid_weight']})
            allpoints.append({'h_wall_m':h,**entry})
        tables={name:m.table(rows,base,widths) for name,rows in samples.items()}
        out['heights'][str(h)]={'h_wall_m':h,'label_z_1m':label1,'label_z_05m':label05,'baseline_1m':{'MAE':tables['primary']['total']['MAE_1'],'ratio_total':tables['primary']['total']['ratio_total_1'],'N':80},'tables':tables}
        assert tables['primary']['total']['MAE_1']==tables['control']['total']['MAE_1']
        print('HEIGHT_DONE',h,'baseline MAE',tables['primary']['total']['MAE_1'],'wide delta_r',tables['primary']['groups']['>=15']['delta_r'],flush=True)
    (R/'points_all_heights.json').write_text(json.dumps(allpoints,indent=2)+'\n')
    (R/'result.json').write_text(json.dumps(out,indent=2)+'\n')
    print('T2C_DONE',json.dumps({'baseline_check_max_abs_diff':out['baseline_label_z2_check']['max_abs_diff'],'first_fluid_k':[x['first_fluid']['k'] for x in levels],'h':{k:{'baseline_mae':v['baseline_1m']['MAE'],'primary_wide_delta_r':v['tables']['primary']['groups']['>=15']['delta_r'],'control_wide_delta_r':v['tables']['control']['groups']['>=15']['delta_r']} for k,v in out['heights'].items()}}),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        (R/'failure_traceback.txt').write_text(traceback.format_exc());raise
