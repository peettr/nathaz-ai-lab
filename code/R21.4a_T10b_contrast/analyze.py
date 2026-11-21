#!/usr/bin/env python3
"""T10b: prescribed contrast, read-only sources; stdlib-only reproducible analysis."""
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / '06_Logs/R21.4a_T10a_error_structure'
spec = importlib.util.spec_from_file_location('t10a_reader', SRC / 'analyze.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def quantile(values, frac):
    v = sorted(values)
    at = (len(v)-1)*frac
    lo = int(at)
    return v[lo] + (v[min(lo+1,len(v)-1)]-v[lo])*(at-lo)


def mean(values):
    assert values
    return sum(values)/len(values)


def contrast(res, dense, sparse):
    d, s = mean([res[i] for i in dense]), mean([res[i] for i in sparse])
    return {'n_dense':len(dense),'n_sparse':len(sparse),
            'mean_dense_e':d,'mean_sparse_e':s,'C':s-d}


def build():
    widths = reader.load_widths()
    ids = sorted(widths)
    assert len(ids)==80
    x = {k:{i:float(widths[i][k]) for i in ids}
         for k in ('disk50_cover','width_min_m','wall_m')}
    for field in x.values():
        assert all(math.isfinite(z) for z in field.values())
    median_disk = quantile(list(x['disk50_cover'].values()), .5)
    median_width = quantile(list(x['width_min_m'].values()), .5)
    dense = [i for i in ids if x['disk50_cover'][i]>=median_disk]
    sparse = [i for i in ids if x['disk50_cover'][i]<median_disk]
    width_dense = [i for i in ids if x['width_min_m'][i]<median_width]
    width_sparse = [i for i in ids if x['width_min_m'][i]>=median_width]
    q1,q2 = [quantile(list(x['wall_m'].values()),q) for q in (1/3,2/3)]
    wall_groups = {'near': [i for i in ids if x['wall_m'][i]<=q1],
                   'middle':[i for i in ids if q1<x['wall_m'][i]<=q2],
                   'far':[i for i in ids if x['wall_m'][i]>q2]}
    configs = {'off_s100':reader.from_t2c('baseline_1m'),
               'off_s101':reader.rows_points(reader.T5/'E_s101_off_points80.json'),
               'off_s102':reader.rows_points(reader.T5/'E_s102_off_points80.json'),
               'off_s103':reader.from_t2d(),
               'fine_0p5':{int(r['id']):(float(r['fine']['primary']['Su'])/reader.U,float(r['obs']))
                            for r in reader.read(reader.T2) if r['h_wall_m']==2.0}}
    expected = {}
    for line in (SRC/'INPUT_SHA256.txt').read_text().splitlines():
        h,p = line.split('  ',1)
        expected[p] = h
    for p,h in reader.used.items():
        assert expected[p]==h,(p,h,expected.get(p))
    assert all(set(c)==set(ids) for c in configs.values())
    obs = {i:configs['off_s100'][i][1] for i in ids}
    assert all(all(math.isfinite(p) and math.isfinite(o) and abs(o-obs[i])<1e-11
                   for i,(p,o) in c.items()) for c in configs.values())
    results = {}
    wall_table = {}; width_table = {}; a1_table = {}
    for name, data in configs.items():
        a = sum(p*o for p,o in data.values())/sum(p*p for p,o in data.values())
        res = {i:a*data[i][0]-data[i][1] for i in ids}
        raw = {i:data[i][0]-data[i][1] for i in ids}
        c = contrast(res,dense,sparse)
        results[name] = {'a_80':a,**c,
                         'per_config_verdict': '满足放大条件' if c['mean_dense_e']<0 and c['mean_sparse_e']>0 and c['C']>=.06 else ('C<0.03' if c['C']<.03 else '未满足放大条件')}
        wall_table[name] = {key:{'n':len(group),'mean_e':mean([res[i] for i in group])}
                            for key,group in wall_groups.items()}
        width_table[name] = contrast(res,width_dense,width_sparse)
        a1_table[name] = {'a_80':1,'disk50_cover':contrast(raw,dense,sparse),
                          'width_min_m':contrast(raw,width_dense,width_sparse),
                          'wall_m':{key:{'n':len(group),'mean_e':mean([raw[i] for i in group])}
                                    for key,group in wall_groups.items()}}
    bases = [results[f'off_s{s}'] for s in range(100,104)]
    amplified = all(r['per_config_verdict']=='满足放大条件' for r in bases)
    avg = mean([r['C'] for r in bases]); fine=results['fine_0p5']['C']
    q1_verdict = '1 m 放大对比' if amplified else ('不放大' if any(r['C']<.03 for r in bases) else '中间')
    q2_verdict = '0.5 m 缩小对比' if amplified and fine<=.5*avg else '不满足缩小判据'
    return {'design':str(ROOT/'04_Decisions/R21.4a_T10b_疏密对比放大检验_设计与判据_20261117.md'),
            'Uref':reader.U,'classification':{'disk50_cover_median':median_disk,'dense_rule':'disk50_cover >= median (ties dense)',
            'dense_ids':dense,'sparse_ids':sparse,'n_dense':len(dense),'n_sparse':len(sparse)},
            'configs':results,'verdict':{'one_meter':q1_verdict,'fine_half_meter':q2_verdict,
            'mean_C_1m':avg,'half_mean_C_1m':.5*avg,'C_0p5':fine},
            'other_tables':{'wall_m_tertiles':{'cutoffs':[q1,q2], 'boundary':'<= lower, (lower, upper], > upper', 'rows':wall_table},
            'width_min_m_median':{'median':median_width,'dense_rule':'width_min_m < median','rows':width_table},
            'a_equals_1':a1_table},'input_sha256':dict(sorted(reader.used.items())),
            'notes':['a_80 is computed across all 80 points; residual e_i=a_80*(Su_i/Uref)-obs_i.',
                     'Secondary tables are descriptive only; 0.5 m is a composite change, not a single-factor mechanism.']}


def main():
    result = build()
    (HERE/'T10b_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    v=result['verdict']; cl=result['classification']
    lines=['# T10b 疏密对比结果','',
           '定义：p=Su/3.9286416，a₈₀=Σpo/Σp²，e=a₈₀p−o，C=mean_疏(e)−mean_密(e)。分类固定，不随配置变化。',
           f"disk50_cover 中位数 {cl['disk50_cover_median']:.9f}；密（≥中位数，含并列）{cl['n_dense']} 点，疏 {cl['n_sparse']} 点。",'',
           '| 配置 | a₈₀ | 密平均残差 | 疏平均残差 | C | 单配置条件 |','|---|---:|---:|---:|---:|---|']
    for name,r in result['configs'].items():
        lines.append(f"| {name} | {r['a_80']:.6f} | {r['mean_dense_e']:.6f} | {r['mean_sparse_e']:.6f} | {r['C']:.6f} | {r['per_config_verdict']} |")
    lines += ['',f"1 m：{v['one_meter']}。四种子平均 C={v['mean_C_1m']:.6f}。",
              f"0.5 m：{v['fine_half_meter']}；C={v['C_0p5']:.6f}，一半基线均值={v['half_mean_C_1m']:.6f}。",'',
              '另报一：wall_m 三分位（线性插值 1/3、2/3 分位；边界划入较近档）',
              '| 配置 | 近 n/mean(e) | 中 n/mean(e) | 远 n/mean(e) |','|---|---:|---:|---:|']
    for name,t in result['other_tables']['wall_m_tertiles']['rows'].items():
        lines.append('| '+name+' | '+' | '.join(f"{t[k]['n']}/{t[k]['mean_e']:.6f}" for k in ('near','middle','far'))+' |')
    lines += ['',f"另报二：width_min_m 中位数 {result['other_tables']['width_min_m_median']['median']:.9f}，窄（<中位数）与宽（≥中位数）。",
              '| 配置 | 窄 n/mean(e) | 宽 n/mean(e) | C宽−窄 |','|---|---:|---:|---:|']
    for name,t in result['other_tables']['width_min_m_median']['rows'].items():
        lines.append(f"| {name} | {t['n_dense']}/{t['mean_dense_e']:.6f} | {t['n_sparse']}/{t['mean_sparse_e']:.6f} | {t['C']:.6f} |")
    lines += ['', '另报三：a=1 不扣整体比例（同时列 disk50_cover、width_min_m 对比；三分位见 JSON）',
              '| 配置 | disk 密平均 | disk 疏平均 | disk C | width 窄平均 | width 宽平均 | width C |','|---|---:|---:|---:|---:|---:|---:|']
    for name,t in result['other_tables']['a_equals_1'].items():
        d,w=t['disk50_cover'],t['width_min_m']
        lines.append(f"| {name} | {d['mean_dense_e']:.6f} | {d['mean_sparse_e']:.6f} | {d['C']:.6f} | {w['mean_dense_e']:.6f} | {w['mean_sparse_e']:.6f} | {w['C']:.6f} |")
    lines += ['','原始输入路径和 SHA256 见 T10b_result.json；只读原数据，零 GPU。相关性不构成因果归因。','']
    (HERE/'RESULT_REPORT.md').write_text('\n'.join(lines))
    print('verdict',v,'counts',cl['n_dense'],cl['n_sparse'],'inputs',len(result['input_sha256']))

if __name__=='__main__': main()
