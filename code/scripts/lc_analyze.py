"""Apply pre-registered learning-curve readings (card 06_Logs/L26.3/lc/EXPERIMENT_CARD.md).
Usage: python lc_analyze.py <out_dir> <j3_fits_dir>"""
import collections, glob, json, os, sys
from lc_common import CFG

def stab_reading(s8, smax):
    if smax >= 3 and smax >= s8 + 2: return '变稳'
    if smax <= 2: return '未变稳'
    return '不判（变化小）'

def main(out, j3):
    B = json.load(open(os.path.join(out, 'base_sindy.json')))
    P = collections.defaultdict(list)
    for f in glob.glob(os.path.join(out, '*_N*_s*.json')):
        r = json.load(open(f)); P[(r['ds'], r['target'], r['N'])].append(r)
    for t in ('mean_f3', 'std_f3'):       # hr N=22 == J3 scheme H2 (same split, same config)
        for f in glob.glob(os.path.join(j3, f'{t}_H2_s*.json')):
            r = json.load(open(f)); P[('hr', t, 22)].append(dict(rmse_test=r['rmse_test'], n_consts=r['n_consts'], canon=r['canon'], loose=r['loose'], plausible=r['plausible'], reused='J3'))
    L = ['| 库 | 目标 | N | 最佳基线 RMSE(参数) | PySR 中位 RMSE / 比值 | PySR 同构最多(严格/宽松)/5 | SINDy RMSE / 比值 / 项数 | SINDy 自助最多相同/5 | PySR 种子数 |', '|' + '---|' * 9]
    summ = {}
    for ds, cfg in CFG.items():
        for t in cfg['targets']:
            rows = []
            for N in cfg['Ns']:
                b = B[f'{ds}|{t}|{N}']; base = b['baseline']; s = b['sindy']; runs = sorted(P[(ds, t, N)], key=lambda r: r['rmse_test'])
                if len(runs) < 5: L.append(f'| {ds} | {t} | {N} | 缺 PySR 结果（{len(runs)}/5） |'); rows.append(None); continue
                med = runs[2]; g = collections.Counter(r['canon'] for r in runs).most_common(1)[0][1]; gl = collections.Counter(tuple(r['loose']) for r in runs).most_common(1)[0][1]
                rows.append(dict(N=N, p_rmse=med['rmse_test'], p_ratio=med['rmse_test'] / base['best_rmse'], p_top=g, p_loose=gl,
                                 s_rmse=s['rmse_test'], s_ratio=s['rmse_test'] / base['best_rmse'], s_n=s['n_terms'], s_top=s['boot_top'], s_edge=s['thr_at_edge']))
                x = rows[-1]
                L.append(f"| {ds} | {t} | {N} | {base['best_rmse']:.4f}({base['best_n']}) | {x['p_rmse']:.4f} / {x['p_ratio']:.3f} | {g} / {gl} | {x['s_rmse']:.4f} / {x['s_ratio']:.3f} / {x['s_n']}{'（阈值贴边）' if x['s_edge'] else ''} | {x['s_top']} | {len(runs)} |")
            ok = [r for r in rows if r]
            if len(ok) == len(rows):
                a, z = ok[0], ok[-1]
                summ[f'{ds}|{t}'] = dict(pysr_stab=stab_reading(a['p_top'], z['p_top']), sindy_stab=('不判（阈值贴边）' if (a['s_edge'] or z['s_edge']) else stab_reading(a['s_top'], z['s_top'])),
                                         pysr_acc='变准' if z['p_rmse'] <= 0.8 * a['p_rmse'] else '未变准',
                                         sindy_acc='变准' if z['s_rmse'] <= 0.8 * a['s_rmse'] else '未变准',
                                         pysr_rmse_ratio_last_first=z['p_rmse'] / a['p_rmse'], sindy_rmse_ratio_last_first=z['s_rmse'] / a['s_rmse'])
    L += ['', '| 库 \\| 目标 | PySR 稳定性 | SINDy 稳定性 | PySR 准确度（RMSE 末/首） | SINDy 准确度（RMSE 末/首） |', '|---|---|---|---|---|']
    for k, v in summ.items():
        L.append(f"| {k} | {v['pysr_stab']} | {v['sindy_stab']} | {v['pysr_acc']}（{v['pysr_rmse_ratio_last_first']:.3f}） | {v['sindy_acc']}（{v['sindy_rmse_ratio_last_first']:.3f}） |")
    for ds in CFG:
        st = [summ.get(f'{ds}|{t}', {}).get('pysr_stab') for t in CFG[ds]['targets']]
        if None in st: L.append(f'{ds}：结果不全，不作库级读法'); continue
        L.append(f"{ds} 库级读法（PySR）：" + ('几何数是本配置结构不稳定的限制因素之一（该库，≥1 个目标量变稳）' if '变稳' in st else
                 ('在所测 N 范围内增加几何数不改善结构稳定性（两个目标量都未变稳）' if all(x == '未变稳' for x in st) else '不判')))
    txt = '\n'.join(L); print(txt); open(os.path.join(out, 'lc_verdict.md'), 'w').write(txt + '\n')
    json.dump(summ, open(os.path.join(out, 'lc_summary.json'), 'w'), indent=1)

if __name__ == '__main__':
    main(*sys.argv[1:3])
