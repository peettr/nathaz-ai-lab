#!/usr/bin/env python3
"""T12 frozen paired z=2.5 m contrasts, following T10b classification."""
import csv,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent; LOG=HERE.parents[1]; U=3.9286416
SOURCE=HERE/'B2u_z2p5_80.json'; POINTS=LOG/'tacc_feasibility/T2c_post/out_3694005/points_all_heights.json'; WIDTHS=LOG/'tacc_feasibility/T2c_post/widths.csv'; T10=LOG/'R21.4a_T10b_contrast/T10b_result.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def calc(p,obs,dense,sparse):
    a=sum(p[i]*obs[i] for i in obs)/sum(p[i]**2 for i in obs)
    e={i:a*p[i]-obs[i] for i in obs}
    d=sum(e[i] for i in dense)/len(dense); s=sum(e[i] for i in sparse)/len(sparse)
    return {'a_80':a,'mean_dense_e':d,'mean_sparse_e':s,'C':s-d}
def main():
    sample=json.loads(SOURCE.read_text()); assert len(sample['rows'])==80 and sample['label_z_m']==2.5
    assert SOURCE.with_name(SOURCE.name+'.sha256').read_text().strip()==f'{sha(SOURCE)}  {SOURCE.name}'
    rows={r['id']:r for r in sample['rows']}; base={r['id']:r for r in json.loads(POINTS.read_text()) if r['h_wall_m']==2.0}; width={int(r['id']):r for r in csv.DictReader(WIDTHS.open())}
    cl=json.loads(T10.read_text())['classification'];dense=cl['dense_ids'];sparse=cl['sparse_ids']; assert len(rows)==len(base)==len(width)==80 and set(rows)==set(base)==set(width)==set(dense+sparse)
    diff={i:rows[i]['speed_mean_mps']-base[i]['baseline_1m']['Su'] for i in rows}; maxdiff=max(abs(x) for x in diff.values());assert maxdiff<=1e-6,maxdiff
    obs={i:float(base[i]['obs']) for i in rows}; su={i:base[i]['baseline_1m']['Su']/U for i in rows};k={i:rows[i]['k_m2s2'] for i in rows}
    up={i:math.sqrt((base[i]['baseline_1m']['Su'])**2+2*k[i])/U for i in rows}
    rms={i:math.sqrt(max(0,rows[i]['speed2_mean_m2s2']))/U for i in rows}
    avg={i:math.sqrt(sum(x*x for x in rows[i]['u_avg_mps']))/U for i in rows}
    stats={key:calc(val,obs,dense,sparse) for key,val in [('Su',su),('S_up',up),('S_rms',rms),('u_avg_magnitude',avg)]}
    c=stats['S_up']['C']; ref=stats['Su']['C']; assert abs(ref-json.loads(T10.read_text())['configs']['off_s100']['C'])<1e-12
    verdict='解析脉动口径可解释对比' if c<=.5*ref else '解析脉动口径不能解释' if c>=.8*ref else '中间'
    # k_need is the additional k per dense point required to cancel dense mean residual,
    # after replacing all 80 speeds by S_up and refitting the global a_80.
    # Solve a scalar additive k to all dense points with a fresh global least-squares fit.
    def fit_extra(extra):
        p={i:math.sqrt((base[i]['baseline_1m']['Su'])**2+2*(k[i]+(extra if i in dense else 0)))/U for i in rows}
        return calc(p,obs,dense,sparse)['mean_dense_e']
    initial=fit_extra(0.0); hi=1.;
    if initial<0:
        while fit_extra(hi)<0 and hi<1e12:hi*=2
        assert hi<1e12
        lo=0.
        for _ in range(90):
            mid=(lo+hi)/2
            if fit_extra(mid)<0:lo=mid
            else:hi=mid
        need=(lo+hi)/2
    else:need=0.
    per={str(i):{'k_res_m2s2':k[i],'k_need_extra_m2s2':need,'k_need_over_k_res':need/k[i] if k[i]>0 else None} for i in dense}
    valid=[v['k_need_over_k_res'] for v in per.values() if v['k_need_over_k_res'] is not None]
    result={'status':'complete','verdict':verdict,'Uref_mps':U,'source':sample['source_vtk'],'source_bytes':sample['source_bytes'],'VTK_label_z_m':2.5,'baseline_speed_mean_max_abs_diff_mps':maxdiff,'baseline_speed_mean_per_point_diff_mps':{str(i):diff[i] for i in rows},'n_dense':len(dense),'n_sparse':len(sparse),'statistics':stats,'C_S_up_over_C_Su':c/ref,'k_need_definition':'uniform extra k applied to all dense points, solve mean_dense(e)=0 with a_80 refitted at each trial','k_need_extra_m2s2':need,'k_need_over_k_res_mean_of_dense_point_ratios':sum(valid)/len(valid) if valid else None,'k_need_over_mean_k_res_dense':need/(sum(k[i] for i in dense)/len(dense)),'k_need_dense_points':per,'input_sha256':{str(p):sha(p) for p in (SOURCE,POINTS,WIDTHS,T10)}}
    dst=HERE/'T12_result_v2.json';dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('T12B',verdict,'C(Su)',ref,'C(S_up)',c,'C(S_rms)',stats['S_rms']['C'],'C(|u_avg|)',stats['u_avg_magnitude']['C'],'k_need',need,'maxdiff',maxdiff,flush=True)
if __name__=='__main__':main()
