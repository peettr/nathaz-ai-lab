"""L26.3 apply pre-registered criteria. Usage: python -I analyze.py results_dir"""
import json, glob, os, sys, collections
from common import TARGETS, SEEDS

def main(d):
    B = json.load(open(os.path.join(d, 'baselines.json')))
    R = {}
    for f in glob.glob(os.path.join(d, '*_s*.json')):
        r = json.load(open(f)); R[(r['target'], r['scheme'], r['seed'])] = r
    lines = ['| 目标 | 留出 | 最佳基线(参数) RMSE | PySR 中位种子 RMSE / 常数 | 不劣(1.05×) | 严格(1.00×) | 项数 | 量纲 | 同构最大组(严格/宽松) |', '|' + '---|' * 9]
    verdict = {}
    for t in TARGETS:
        passes = []
        for s in ('H1', 'H2'):
            b = B[f'{t}_{s}']; runs = [R[(t, s, k)] for k in SEEDS if (t, s, k) in R]
            if not runs: lines.append(f'| {t} | {s} | 缺 PySR 结果 |'); passes.append(False); continue
            runs.sort(key=lambda r: r['rmse_test']); med = runs[len(runs) // 2]
            nf = med['rmse_test'] <= 1.05 * b['best_rmse']; strict = med['rmse_test'] <= b['best_rmse']
            nc = med['n_consts'] <= b['best_nparams']
            pl = med['plausible']
            g = collections.Counter(r['canon'] for r in runs).most_common(1)[0][1]
            gl = collections.Counter(tuple(r['loose']) for r in runs).most_common(1)[0][1]
            row = dict(nf=nf, nc=nc, pl=pl, iso=g >= 3)
            passes.append(row)
            lines.append(f"| {t} | {s} | {b['best']}({b['best_nparams']}) {b['best_rmse']:.4f} | {med['rmse_test']:.4f} / {med['n_consts']} | {'是' if nf else '否'} | {'是' if strict else '否'} | {'是' if nc else '否'} | {'是' if pl else '否'} | {g}/{gl} |")
        ok = all(isinstance(p, dict) for p in passes) and all(p['nf'] and p['nc'] for p in passes) and passes[0]['pl'] and passes[1]['pl'] and passes[0]['iso']
        verdict[t] = ok
    missing = [k for t in TARGETS for s in ('H1','H2') for k in [(t,s)] if not any((t,s,sd) in R for sd in SEEDS)]
    n = sum(verdict.values())
    if missing:
        lines += ['', f'结果不全（缺 {len(missing)} 组），不作判定']
        out='\n'.join(lines); print(out); open(os.path.join(d,'verdict.md'),'w').write(out+'\n'); return
    lines += ['', '目标量通过：' + '，'.join(f'{t} {"通过" if v else "不通过"}' for t, v in verdict.items()),
              f'通过 {n}/4 → {"值得用" if n >= 2 else "放弃"}（判据：≥2 个通过）']
    out = '\n'.join(lines); print(out); open(os.path.join(d, 'verdict.md'), 'w').write(out + '\n')

if __name__ == '__main__':
    main(sys.argv[1])
