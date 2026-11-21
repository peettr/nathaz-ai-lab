#!/usr/bin/env python3.10
"""Reduce only SHA-verified, real two-seed T13 evidence. No fixture fallback."""
import csv,hashlib,json,math,pathlib
R=pathlib.Path(__file__).resolve().parent
ROOT=R.parents[2]
T5=ROOT/'06_Logs/R21.4a_T5_caseE_WM_retry2/evidence'
T10=ROOT/'06_Logs/R21.4a_T10b_contrast/T10b_result.json'
W=ROOT/'06_Logs/tacc_feasibility/T2c_post/widths.csv'
U=3.9286416
FROZEN={101:'6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279',102:'b284b8075072e0c162773096c4b7ba1547f0dc41517b461058803d16d82b8bcf'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verified(p):
    assert p.is_file() and p.stat().st_size>0,p
    assert sha(p)==(p.parent/(p.name+'.sha256')).read_text().strip(),p
    return p

def points(p):
    q=json.loads(p.read_text());rows={int(x['id']):x for x in q['rows']}
    assert set(rows)==set(range(1,81))
    return rows

def main():
    runs=[p for p in R.glob('run_luw-t13-a100-*/evidence') if (p/'run.done').is_file()]
    assert len(runs)==1,('expected one completed evidence root',runs)
    E=runs[0]
    done=json.loads(verified(E/'run.done').read_text())
    assert done['verified_cases']==['E_s101_off','E_s102_off'] and done['mode']=='production'
    widths={int(r['id']):r for r in csv.DictReader(W.open(encoding='utf-8-sig'))}
    assert set(widths)==set(range(1,81))
    t10=json.loads(T10.read_text())
    dense=t10['classification']['dense_ids'];sparse=t10['classification']['sparse_ids']
    assert len(dense)==len(sparse)==40
    wide=sorted(i for i in widths if float(widths[i]['width_min_m'])>=15)
    far=[31,39,40,47,48,49,65,66,69,77,79]
    assert len(wide)==64 and len(far)==11
    sources={str(T10):sha(T10),str(W):sha(W)}
    cases={};delta=[]
    for seed in (101,102):
        name=f'E_s{seed}_off';b=T5/(name+'_points80.json')
        assert sha(b)==FROZEN[seed]
        p=verified(E/(name+'_points80.json'))
        slice_=verified(E/(name+'_upstream_slice.npz'))
        pr=verified(E/(name+'_profile.json'))
        log=verified(E/(name+'_solver.log'))
        assert 'NVIDIA A100-SXM4-40GB' in log.read_text(errors='replace')
        assert json.loads(verified(E/(name+'_exit.json')).read_text())['solver_exit']==0
        sources.update({str(x):sha(x) for x in (b,p,slice_,pr,log)})
        on=points(p);off=points(b)
        assert all(abs(on[i]['obs']-off[i]['obs'])<1e-12 for i in on)
        profile=json.loads(pr.read_text())['profile']
        assert len(profile)==18 and all(math.isfinite(x['kappa']) and math.isfinite(x['U_ratio']) for x in profile)
        gate={str(x['height_agl_m']):x['kappa'] for x in profile if x['x_m']==45 and x['height_agl_m'] in (10,15.9)}
        assert len(gate)==2
        operation=all(.85<=v<=1.25 for v in gate.values())
        def metrics(q):
            p={i:q[i]['Su']/U for i in q};o={i:q[i]['obs'] for i in q}
            a=sum(p[i]*o[i] for i in p)/sum(x*x for x in p.values())
            e={i:a*p[i]-o[i] for i in p}
            md=sum(e[i] for i in dense)/len(dense);ms=sum(e[i] for i in sparse)/len(sparse)
            return dict(a_80=a,C=ms-md,mean_dense_e=md,mean_sparse_e=ms,
                MSE_pat_80=sum(x*x for x in e.values())/80,
                MAE=sum(abs(p[i]-o[i]) for i in p)/80,
                r_wide=sum(p[i] for i in wide)/sum(o[i] for i in wide),
                r_N_far=sum(p[i] for i in far)/sum(o[i] for i in far))
        mo=metrics(on);mb=metrics(off);assert abs(mb['C']-t10['configs'][f'off_s{seed}']['C'])<1e-12
        d=mo['C']-mb['C'];delta.append(d)
        cases[str(seed)]={'operation_gate_x45':gate,'operation_pass':operation,
            'off':mb,'T13':mo,'delta_C':d,'delta_MSE_pat_80':mo['MSE_pat_80']-mb['MSE_pat_80'],
            'upstream_profile':profile,'point_sha256':sha(p),'slice_sha256':sha(slice_)}
    passed=all(v['operation_pass'] for v in cases.values())
    verdict=('操作未达，不判' if not passed else
        '来流湍流是疏密对比的杠杆' if sum(delta)/2<=-.04 and all(d<=-.02 for d in delta) else
        '来流湍流不是杠杆' if all(abs(d)<.016 for d in delta) else '中间')
    out={'definition':{'p':'Su/Uref','Uref':U,'a_80':'sum(p*obs)/sum(p²)','e':'a_80*p-obs',
        'C':'mean_sparse(e)-mean_dense(e)','MSE_pat_80':'mean(e²)','R_pat':.002408262},
        'cases':cases,'mean_delta_C':sum(delta)/2,'operation_pass':passed,'verdict':verdict,'input_sha256':sources}
    path=R/'T13_verdict.json';assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('T13',verdict,'mean_delta_C',out['mean_delta_C'])
    for s,v in cases.items():print(s,'kappa',v['operation_gate_x45'],'C',v['T13']['C'],'delta_C',v['delta_C'],'delta_MSE_pat',v['delta_MSE_pat_80'])
if __name__=='__main__':main()
