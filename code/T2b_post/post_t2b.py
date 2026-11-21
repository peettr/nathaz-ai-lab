#!/usr/bin/env python3
"""T2b read-only post: reuse frozen T2 v4 utilities, add native-flag diagnostics."""
import csv, hashlib, itertools, json, math, pathlib, sys, time, traceback
import numpy as np
from scipy.ndimage import distance_transform_edt
import post_t2 as m
R=pathlib.Path(__file__).resolve().parent
SOURCE=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2b_05m')
PREVIOUS=pathlib.Path('/scratch/04448/[用户]/r24_luw/T2_05m_post_v4')
m.VTKS=[SOURCE/'case_4gpu/RESULTS/vtk/20251222120000_avg-000062000.vtk',
        pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk')]
m.STL=SOURCE/'case_4gpu/proj_temp/CaseE_PF.stl'
FLAGS=SOURCE/'case_4gpu/RESULTS/native_flags_nearground_z43_45.bin'
# Small immutable inputs are copied into this fresh run root, never mutated at source.

def check():
    for p in (*m.VTKS,m.STL,FLAGS,R/'B2u_reference_points.json',R/'baseline.csv',R/'widths.csv'):
        assert p.is_file(),str(p)
    assert FLAGS.stat().st_size==3000000
    v2,v1=map(m.vtk_open,m.VTKS)
    assert v2['dims']==(1000,1000,540) and v2['origin']==(0.,0.,-20.) and v2['spacing']==(.5,)*3
    assert v1['dims']==(500,500,270) and v1['spacing']==(1.,)*3
    return v2,v1

def flags_diag(rows,flags):
    # Exact nearest 2D native solid per exported z slice, x-fastest flag layout.
    indices=[]
    for k in (43,44,45):
        solid=(flags[k-43]&1)!=0
        assert solid.any(),k
        _,ind=distance_transform_edt(~solid,return_indices=True)
        indices.append(ind)
    out=[]
    for p in rows:
        x,y=p['xls_xy']; x+=1010.50008-760+.5;y+=1000.60004-750+.5
        i,j=round(x/.5),round(y/.5)
        point={'id':p['id'],'sample_xy_m':[x,y],'layers':[]}
        for k in (43,44,45):
            assert 0<=i<1000 and 0<=j<1000
            f=flags[k-43];solid=bool(int(f[j,i])&1)
            sj,si=(int(a[j,i]) for a in indices[k-43]);di,dj=i-si,j-sj
            distance_cells=math.hypot(di,dj)
            near={'distance_m':distance_cells*.5,'distance_cells':distance_cells,
                  'fluid_layer_ordinal_2d':math.ceil(distance_cells),
                  'normal_from_solid_xy':[di,dj], 'solid_index':[si,sj]}
            point['layers'].append({'k_global':k,'z_m':-20+.5*k,'native_flag':int(f[j,i]),'solid':solid,
                'nearest_solid_2d':near,
                'censor':'exact nearest in this exported horizontal plane only; k<43 and full 3D nearest wall unavailable'})
        out.append(point)
    return out

def inlet(v2,v1):
    ys=[80.,120.,180.,250.,320.,380.,420.];records=[]
    for h in (1.5,2.,5.,10.,15.9):
        pairs=[]
        for v in (v2,v1):
            dx=v['spacing'][0];i=round((2-v['origin'][0])/dx);a=(h-v['origin'][2])/dx;k=math.floor(a);w=a-k
            samples=[]
            for y in ys:
                j=round((y-v['origin'][1])/dx)
                u=np.asarray((1-w)*v['fields']['u_avg'][k,j,i]+w*v['fields']['u_avg'][k+1,j,i],dtype=float)
                kk=float((1-w)*v['fields']['tke'][k,j,i]+w*v['fields']['tke'][k+1,j,i])
                assert np.isfinite(u).all() and math.isfinite(kk)
                samples.append({'y_m':y,'U_components_raw':u.tolist(),'U_norm_raw':float(np.linalg.norm(u)),'k_raw':kk})
            pairs.append({'dx_m':dx,'samples':samples,'mean_U_components_raw':np.mean([x['U_components_raw'] for x in samples],axis=0).tolist(),'mean_U_norm_raw':float(np.mean([x['U_norm_raw'] for x in samples])),'mean_k_raw':float(np.mean([x['k_raw'] for x in samples]))})
        records.append({'h_m':h,'pairs':pairs,'U_ratio':pairs[0]['mean_U_norm_raw']/pairs[1]['mean_U_norm_raw'],'k_ratio':pairs[0]['mean_k_raw']/pairs[1]['mean_k_raw'] if pairs[1]['mean_k_raw'] else None})
    return {'x_m':2,'y_m':ys,'quantity':'VTK time-mean field, not imposed inlet table; raw u and resolved tke','rows':records}

def main():
    v2,v1=check();m.ROOT=R
    tri,n=m.triangles(m.STL);ref=json.loads((R/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80
    with (R/'baseline.csv').open(newline='') as f:baseline=list(csv.DictReader(f))
    with (R/'widths.csv').open(newline='') as f:widths=list(csv.DictReader(f))
    flags=np.memmap(FLAGS,mode='r',dtype='u1',shape=(3,1000,1000))
    # Native flag must agree substantially with VTK scalar mask at the exported planes.
    flag_checks=[]
    for k in (43,44,45):
        solid=(flags[k-43]&1)!=0;fluid=np.asarray(v2['fields']['fluid'][k])>.5
        agreement=float(np.mean(solid==~fluid));flag_checks.append({'k':k,'flag_solid':int(solid.sum()),'vtk_solid':int((~fluid).sum()),'agreement':agreement})
        assert agreement>.99,flag_checks
    m.save_json('flag_mask_check.json',flag_checks)
    m.save_json('native_wall_layers.json',{'definition':'exact horizontal 2D nearest solid at each exported native z level; layer ordinal=ceil(distance in cells); vertical k<43 unavailable','rows':flags_diag(ref['rows'],flags)})
    # The alignment is frozen before reading T2b metrics; do not select by fit-to-observation.
    rows=[]
    for p in ref['rows']:
        samples={str(s):m.point_sample(v2,p,s) for s in ((.5,.5,0.),(1.,1.,0.))}
        rows.append({'id':p['id'],'obs':p['after'],'xls_xy':p['xls_xy'],'samples':samples})
    m.save_json('points_primary_control.json',rows)
    def scored(shift):return [{'id':q['id'],'obs':q['obs'],'Su_ratio':q['samples'][str(shift)]['Su']/ref['uref'],'fluid_corners':q['samples'][str(shift)]['fluid_corners'],'solid_weight':q['samples'][str(shift)]['solid_weight']} for q in rows]
    tables={'primary_05_05_0':m.table(scored((.5,.5,0.)),baseline,widths),'control_1_1_0':m.table(scored((1.,1.,0.)),baseline,widths)}
    for t in tables.values():
        for g in t['groups'].values():
            if g['N']:g['ratio_total_definition']='sum(Su/Uref)/sum(obs), not mean(pointwise ratio)'
    m.save_json('result.json',{'tables':tables,'ratio_total_definition':'sum_i (Su_i/Uref) / sum_i obs_i','sources':[{'path':v['path'],'bytes':v['bytes'],'dims':v['dims'],'origin':v['origin'],'spacing':v['spacing']} for v in (v2,v1)],'uref':ref['uref'],'flags':str(FLAGS),'stat_window':'62000 steps; last 40000 stride 80; solver log 500 samples','missing':'T2b four-GPU stepwise trace not measured; cannot certify that prerequisite'})
    m.save_json('inlet_same_height_multiy.json',inlet(v2,v1))
    # Wall-normal diagnostic in the horizontal plane, not replacement for point values.
    wall={p['id']:p for p in json.loads((R/'native_wall_layers.json').read_text())['rows']};diagnostics=[]
    for p in ref['rows']:
        if p['id'] not in (50,51,52,54,55,74):continue
        near=wall[p['id']]['layers'][1]['nearest_solid_2d']; q={'id':p['id'],'measurement_is_unchanged':True,'near':near,'samples_not_measurements':[]}
        di,dj=near['normal_from_solid_xy'];norm=math.hypot(di,dj)
        if norm>0:
            si,sj=near['solid_index']
            for distance in (.5,1.,1.5):
                x=(si+di*distance/.5/norm)*.5;y=(sj+dj*distance/.5/norm)*.5
                synthetic={'xls_xy':[x-(1010.50008-760),y-(1000.60004-750)]}
                q['samples_not_measurements'].append({'normal_distance_from_solid_center_m':distance,'xy_m':[x,y],**m.point_sample(v2,synthetic,(0.,0.,0.))})
        diagnostics.append(q)
    m.save_json('six_nearwall_normal_diagnostic.json',diagnostics)
    planes=[]
    for x in m.write_planes(v2):
        planes.append(x)
        with (R/'planes.progress.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
    m.save_json('result_complete.json',{'tables':tables,'planes':planes,'flag_checks':flag_checks})
    print('POST_DONE',json.dumps({'gates':{k:v['gates'] for k,v in tables.items()},'planes':len(planes)}),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        (R/'failure_traceback.txt').write_text(traceback.format_exc());raise
