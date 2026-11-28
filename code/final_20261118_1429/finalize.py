#!/usr/bin/env python3
"""Finalize T14 without altering the archived T14a or original measurements."""
import csv,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent
U=3.9286416

def load(p):
    b=p.read_bytes()
    return json.loads(b), hashlib.sha256(b).hexdigest()

def metrics(p,obs):
    ids=sorted(p)
    assert ids==sorted(obs)==list(range(1,81))
    ps=[p[i]/U for i in ids];oo=[obs[i] for i in ids]
    assert all(math.isfinite(x) for x in ps+oo)
    a=sum(x*y for x,y in zip(ps,oo))/sum(x*x for x in ps)
    mse=sum((x-y)**2 for x,y in zip(ps,oo))/80
    pat=sum((a*x-y)**2 for x,y in zip(ps,oo))/80
    return a,mse,pat,pat/mse,{i:a*p[i]/U-obs[i] for i in ids}

def main():
    old,h0=load(BASE/'T14_result.json')
    corners,h1=load(HERE/'B2u_corners_z2p5.json')
    expected=(HERE/'B2u_corners_z2p5.json.sha256').read_text().split()[0]
    assert h1==expected
    t2=ROOT/'06_Logs/tacc_feasibility/T2c_post/out_3694005/points_all_heights.json'
    ref,h2=load(t2)
    r={int(x['id']):x for x in ref if x['h_wall_m']==2.0}
    rows={int(x['id']):x for x in corners['rows']}
    assert set(r)==set(rows)==set(range(1,81)) and corners['label_z_m']==2.5
    dmax=max(abs(rows[i]['old_speed_mean_mps']-r[i]['baseline_1m']['Su']) for i in r)
    assert dmax<=1e-6,dmax
    assert all(rows[i]['fluid_corners']==r[i]['baseline_1m']['fluid_corners'] for i in r)
    assert all(max(abs(a-b) for a,b in zip(rows[i]['xyz_m'],r[i]['baseline_1m']['xyz_m']))<1e-10 for i in r)
    oldp={i:r[i]['baseline_1m']['Su'] for i in r}
    newp={i:rows[i]['new_speed_mean_mps'] for i in r}
    obs={i:r[i]['obs'] for i in r}
    widths=ROOT/'06_Logs/tacc_feasibility/T2c_post/widths.csv'
    wb=widths.read_bytes();wh=hashlib.sha256(wb).hexdigest()
    cv={int(x['id']):float(x['disk50_cover']) for x in csv.DictReader(wb.decode('utf-8-sig').splitlines())}
    assert set(cv)==set(r)
    v=sorted(cv.values()); med=(v[39]+v[40])/2
    dense=[i for i in sorted(r) if cv[i]>=med];sparse=[i for i in sorted(r) if cv[i]<med]
    assert len(dense)+len(sparse)==80
    def evaluate(p):
        a,mse,pat,phi,e=metrics(p,obs)
        ed=sum(e[i] for i in dense)/len(dense);es=sum(e[i] for i in sparse)/len(sparse)
        return {'a_80':a,'MSE':mse,'MSE_pat':pat,'phi':phi,'mean_dense_e':ed,'mean_sparse_e':es,'C':es-ed}
    affected=[{'id':i,'fluid_corners':rows[i]['fluid_corners'],'delta_Su_mps':newp[i]-oldp[i]} for i in sorted(r) if rows[i]['fluid_corners']<8]
    assert all(abs(newp[i]-oldp[i])<1e-10 for i in r if rows[i]['fluid_corners']==8)
    before=evaluate(oldp);after=evaluate(newp)
    other={s:'无本地平均场角点，不能实施替代取样' for s in ('s101','s102','s103')}
    inp=dict(old['input_sha256']);inp.update({str(BASE/'T14_result.json'):h0,str(HERE/'B2u_corners_z2p5.json'):h1,str(t2):h2,str(widths):wh})
    out={'design':old['design'],'T14a':old['T14a'],'geometry':old['geometry'],'exclusions':old['exclusions'],
         'T14b':{'s100':{'source':'B2u mean VTK; T2c primary registration z label 2.5 m','n':80,'max_baseline_Su_difference_mps':dmax,'dense_n':len(dense),'sparse_n':len(sparse),'disk50_median':med,'affected':affected,'before':before,'after':after,'delta':{k:after[k]-before[k] for k in ('C','MSE_pat','phi')},'corner_file_sha256':h1},'other_seeds':other},
         'input_sha256':inp,'resource':{'ComputeOps':'CO-722923ae','TACC_job':'3735719','rc_job_receipt':'已登记：TACC 超算 作业 3735719','remote_root':'/scratch/04448/[用户]/r24_luw/T14b_20261118_142400'},
         'notes':old['notes']+['T14b only changes sampling on the same s100 mean field, not a new simulation.','Case D/BG reported by archived labelled group; repeated physical sites across groups are not independent.']}
    (HERE/'T14_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    (HERE/'INPUT_SHA256.txt').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(inp.items())))
    lines=['# T14 结果（11-18 美东）','','T14a 按归档组分别报告，不跨算例比较绝对误差；重复标签不是独立测点。','', '| 算例组 | n | a | MSE | φ | 判词 | C | 组间占比 |','|---|---:|---:|---:|---:|---|---:|---:|']
    for case,val in old['T14a'].items():
        for group,m in (val.items() if case in ('CaseD','BG_1H','BG_3H') else [('',val)]):
            c=m.get('contrast',{})
            lines.append(f"| {case} {group} | {m['n']} | {m['a']:.6f} | {m['MSE']:.6f} | {m['phi']:.4f} | {m['verdict']} | {c.get('C',float('nan')):.6f} | {c.get('between_fraction',float('nan')):.5f} |")
    lines+=['','T14a 的 Case D/BG disk50_cover 为原建筑 STL z=2 m 切片的 1 m 中心采样近似；中位数并列归密。各组的逐点覆盖率、样本数和排除情况见 JSON。','',
            'T14b 的 s100 同高旧取样与 T2c 逐点最大差 %.3g m/s，80 点均在 1e-6 以内。' % dmax,
            '改变点 ID：'+', '.join(str(x['id']) for x in affected)+'；其余 75 点数值不变。',
            '| s100 | C | MSE_pat | φ | a_80 |','|---|---:|---:|---:|---:|',
            f"| 原取样 | {before['C']:.6f} | {before['MSE_pat']:.6f} | {before['phi']:.6f} | {before['a_80']:.6f} |",
            f"| 只用流体角点 | {after['C']:.6f} | {after['MSE_pat']:.6f} | {after['phi']:.6f} | {after['a_80']:.6f} |",
            's101–s103 未找到同源局部场角点，未作替代取样。原数据不改，TACC 仅 CPU 只读取样；输入及角点 SHA256 见 INPUT_SHA256.txt。','']
    (HERE/'RESULT_REPORT.md').write_text('\n'.join(lines))
    print('T14_FINAL',json.dumps({'cases':len(old['T14a']),'groups':sum(len(v) if k in ('CaseD','BG_1H','BG_3H') else 1 for k,v in old['T14a'].items()),'baseline_maxdiff':dmax,'affected':affected,'before':before,'after':after,'input_count':len(inp)},ensure_ascii=False))
if __name__=='__main__':main()
