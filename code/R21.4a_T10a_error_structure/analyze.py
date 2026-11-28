#!/usr/bin/env python3
"""T10a frozen design, local read-only source analysis (stdlib only)."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
LOG = ROOT / '06_Logs'
U = 3.9286416
T2 = LOG/'tacc_feasibility/T2c_post/out_3694005/points_all_heights.json'
W = LOG/'tacc_feasibility/T2c_post/widths.csv'
T2D = LOG/'tacc_feasibility/T2d_a3/result_3701541.json'
T5 = LOG/'R21.4a_T5_caseE_WM_retry2/evidence'
T6 = LOG/'R21.4a_T6_z0_inlet/evidence'
T7 = LOG/'R21.4a_T7_buffer40_try2/evidence'
T9 = LOG/'R21.4a_T9b_facade_slip_v2/build17_run_20261117_190746/run_luw-t9b17-a100-25014f15/evidence'
FAR = {31,39,40,47,48,49,65,66,69,77,79}
CLOSE = {50,51,52,55,74}
FEATURES = ['wall_m','width_min_m','disk50_cover','upwind_solid_frac','upstream_nearest_solid_m','reverse_ux_proxy']
used = {}
def read(path):
    assert path.is_file(), f'missing source: {path}'
    b = path.read_bytes()
    used[str(path)] = hashlib.sha256(b).hexdigest()
    return json.loads(b)
def rows_points(path):
    return {int(x['id']): (float(x['Su'])/U, float(x['obs'])) for x in read(path)['rows']}
def from_t2c(field):
    rows = [r for r in read(T2) if r['h_wall_m'] == 2.0]
    return {int(r['id']): (float(r[field]['Su'])/U, float(r['obs'])) for r in rows}
def from_t2d():
    h = read(T2D)['heights']['2.0']
    assert h['label_z_m'] == 2.5
    return {int(r['id']): (float(r['new']['Su'])/U, float(r['obs'])) for r in h['points']}
def load_widths():
    b = W.read_bytes(); used[str(W)] = hashlib.sha256(b).hexdigest()
    return {int(r['id']): r for r in csv.DictReader(b.decode('utf-8-sig').splitlines())}
def ranks(seq):
    order = sorted(range(len(seq)), key=lambda i: seq[i]); ans = [None]*len(seq)
    for j,i in enumerate(order):
        if j and seq[i] == seq[order[j-1]]: continue
        end = j + 1
        while end < len(seq) and seq[order[end]] == seq[i]: end += 1
        for k in range(j,end): ans[order[k]] = (j+1+end)/2
    return ans
def spearman(xs,ys):
    x,y = ranks(xs),ranks(ys)
    mx,my = sum(x)/len(x),sum(y)/len(y)
    den = math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))
    return None if not den else sum((a-mx)*(b-my) for a,b in zip(x,y))/den
def calc(data, ids):
    p = [data[i][0] for i in ids]; o = [data[i][1] for i in ids]
    mse = sum((a-b)**2 for a,b in zip(p,o))/len(ids)
    a = sum(x*y for x,y in zip(p,o))/sum(x*x for x in p)
    pat = sum((a*x-y)**2 for x,y in zip(p,o))/len(ids)
    return {'n':len(ids),'MSE':mse,'a_G':a,'MSE_pat':pat,'level_MSE':mse-pat,'phi':pat/mse}
def main():
    widths = load_widths()
    groups = {'all80':sorted(widths),'wide64':sorted(i for i,r in widths.items() if float(r['width_min_m'])>=15), 'N_far':sorted(FAR),'N_close':sorted(CLOSE)}
    assert [len(groups[k]) for k in ('all80','wide64','N_far','N_close')] == [80,64,11,5]
    assert set(i for i in widths if float(widths[i]['width_min_m'])<15) == FAR|CLOSE
    configs = {'off_s100':from_t2c('baseline_1m'), 'off_s103':from_t2d()}
    # fine.primary is nested; use exact main registration, not control.
    configs['fine_0p5'] = {int(r['id']):(float(r['fine']['primary']['Su'])/U,float(r['obs'])) for r in read(T2) if r['h_wall_m']==2.0}
    for seed in (101,102):
        for label,base,state in [('off',T5,'off'),('T5_on',T5,'on'),('T6_on',T6,'on'),('T7',T7,'off'),('T9b_on',T9,'on')]:
            p=base/f'E_s{seed}_{state}_points80.json'
            if p.is_file(): configs[f'{label}_s{seed}']=rows_points(p)
            else: raise FileNotFoundError(p)
    # Independent source cross-checks: T2d old is T2c s100; T2d s102 new is T5 off.
    d103 = read(T2D)['heights']['2.0']['points']
    assert max(abs(r['old']['Su']/U-configs['off_s100'][r['id']][0]) for r in d103) == 0
    d102 = read(LOG/'tacc_feasibility/T2d_a3/result_3701540.json')['heights']['2.0']['points']
    assert max(abs(r['new']['Su']/U-configs['off_s102'][r['id']][0]) for r in d102) == 0
    obs0 = {i:v[1] for i,v in configs['off_s100'].items()}
    for name,data in configs.items():
        assert set(data)==set(groups['all80']), (name,len(data))
        assert all(math.isfinite(p) and math.isfinite(o) and abs(o-obs0[i])<1e-11 for i,(p,o) in data.items()),name
    metrics = {name:{g:calc(data,ids) for g,ids in groups.items()} for name,data in configs.items()}
    baseline = [f'off_s{s}' for s in (100,101,102,103)]
    rpat = max(metrics[k]['all80']['MSE_pat'] for k in baseline)-min(metrics[k]['all80']['MSE_pat'] for k in baseline)
    phis=[metrics[k]['all80']['phi'] for k in baseline]
    q1 = '格局主导' if all(x>=2/3 for x in phis) else ('水平主导' if all(x<=1/3 for x in phis) else '中间')
    comparisons = {}
    for name in configs:
        if name.startswith('off_'): continue
        seed = name.split('_s')[-1] if '_s' in name else '100'
        key = 'off_s'+seed
        delta=metrics[name]['all80']['MSE_pat']-metrics[key]['all80']['MSE_pat']
        comparisons[name]={'reference':key,'delta_MSE_pat_80':delta,'verdict':'格局改善' if delta < -rpat else ('格局变差' if delta > rpat else '格局不变')}
    corr={}
    for name,data in configs.items():
        a=metrics[name]['all80']['a_G'];res={i:a*v[0]-v[1] for i,v in data.items()}
        corr[name]={}
        for feature in FEATURES:
            valid=[]
            for i in groups['all80']:
                raw=widths[i][feature]
                if raw in ('','nan','NaN'): continue
                x = 1.0 if raw=='True' else 0.0 if raw=='False' else float(raw)
                if math.isfinite(x): valid.append((x,res[i]))
            corr[name][feature]={'n':len(valid),'rho':spearman([x for x,y in valid],[y for x,y in valid])}
    result={'design':str(ROOT/'04_Decisions/R21.4a_T10a_误差结构诊断_设计与判据_20261117.md'), 'uref':U,'groups':groups,'metrics':metrics,'R_pat':rpat,'question1':{'phi_baselines':dict(zip(baseline,phis)),'verdict':q1},'question2':comparisons,'spearman_residual_vs_geometry':corr,'input_sha256':used,'notes':['T7 uses off-labeled points80 as delivered; compare with same-seed T5 off.','Spearman uses average ranks for ties; missing feature cells excluded per configuration.','Fine is T2c fine.primary at h_wall_m=2.0.']}
    (OUT/'T10a_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'INPUT_SHA256.txt').open('w') as f:
        for path,h in sorted(used.items()): f.write(h+'  '+path+'\n')
    lines = ['# T10a 结果报告', '', '按 11-17 写定定义，p=Su/3.9286416，MSE=mean((p-o)²)，a=Σpo/Σp²，MSE_pat=mean((ap-o)²)，φ=MSE_pat/MSE。R_pat 是四个 1 m 关闭种子的 80 点 MSE_pat 极差。','','| 配置 | MSE₈₀ | a₈₀ | MSE_pat,80 | φ₈₀ | 配对判词 |','|---|---:|---:|---:|---:|---|']
    for name,bygroup in metrics.items():
        m=bygroup['all80']; v=comparisons.get(name,{}).get('verdict','基线')
        lines.append(f"| {name} | {m['MSE']:.6f} | {m['a_G']:.6f} | {m['MSE_pat']:.6f} | {m['phi']:.4f} | {v} |")
    lines += ['',f'问题 1：{q1}；四基线 φ₈₀=' + ', '.join(f'{k}:{v:.4f}' for k,v in zip(baseline,phis)) + f'；R_pat={rpat:.9f}。', '问题 2：严格超过 R_pat 才判变好或变差；fine_0p5 改善，T6 两种子变差，T5/T7/T9b 两种子均不变。0.5 m 是复合改动，不作单因归因。','', '四组每配置的 MSE、a_G、MSE_pat、水平部分及 φ，逐配置 Spearman 系数与有效样本数均见 T10a_result.json。残差为 a₈₀p−o，Spearman 按平均秩处理并列；几何缺值逐对剔除。相关性只描述，不用于归因。', '源文件绝对路径和 SHA256 见 INPUT_SHA256.txt；T2d s102 与 T5 off s102 的 80 个 Su 完全一致，T2d s103 的旧支与 T2c s100 完全一致。T7 文件名为 off，按其现有两例直接与同种子 T5 off 配对。','所有计算只读原始文件，未开启 GPU。','']
    (OUT/'RESULT_REPORT.md').write_text('\n'.join(lines))
    print('configurations',len(configs),'inputs',len(used),'R_pat',rpat,'Q1',q1)
    for name,v in comparisons.items(): print(name,v)
if __name__=='__main__': main()
