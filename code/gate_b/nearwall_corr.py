"""L22.11 开工闸 (b)：分区界面异常检验（卡 §2）+ 近壁最强梯度单元相关（卡 §3）+ v3 盒 κ（卡 §0）。
判据写定于 EXPERIMENT_CARD_gate_b.md（11-22 08:57），本脚本只计算。只读快试回传文件；工作站 小计算，0 SU。
用法：python3 -I nearwall_corr.py"""
import gzip, io, json, numpy as np, os, hashlib
from scipy.spatial import cKDTree
from scipy.stats import pearsonr, spearmanr
H = os.path.dirname(os.path.abspath(__file__))
Q = './26_Quick_Trials/06_Logs/L26.21/G1/meshconv'
def npy(p): return np.load(io.BytesIO(gzip.open(p).read()))
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
files = {'medium': dict(g=f'{Q}/diag/medium_gradient.npy.gz', perm=f'{Q}/perm/returned/output/medium/medium_perm.npy.gz',
                        cnt=f'{Q}/perm/returned/output/medium/medium_partition_counts.json',
                        C=f'{Q}/geom/returned/medium_centres.npy.gz', V=f'{Q}/geom/returned/medium_volumes.npy.gz'),
         'fine': dict(g=f'{Q}/diag/fine_gradient_final.npy.gz', perm=f'{Q}/perm/returned/output/fine/fine_perm.npy.gz',
                      cnt=f'{Q}/perm/returned/output/fine/fine_partition_counts.json',
                      C=f'{Q}/geom/returned/fine_centres.npy.gz', V=f'{Q}/geom/returned/fine_volumes.npy.gz')}
out = dict(inputs={m: {k: sha(p) for k, p in d.items()} for m, d in files.items()})

def counts(p):
    j = json.load(open(p))
    for k in ('reconstructed_counts', 'original_counts'):
        if isinstance(j, dict) and k in j and isinstance(j[k], list): return np.array(j[k])
    if isinstance(j, list): return np.array(j)
    raise SystemExit(f'counts format? {list(j)[:5]}')

def inbox(C): return (np.abs(C[:, 0]) <= 16) & (np.abs(C[:, 1]) <= 16) & (C[:, 2] >= 0) & (C[:, 2] <= 16)
def wall_dist(P):  # 到建筑长方体 x,y∈[-8,8], z∈[0,8] 外表面距离（不计地面）
    dx = np.maximum(np.abs(P[:, 0]) - 8, 0); dy = np.maximum(np.abs(P[:, 1]) - 8, 0); dz = np.maximum(P[:, 2] - 8, 0)
    return np.sqrt(dx**2 + dy**2 + dz**2)

D = {}
for m, f in files.items():
    gp = npy(f['g']).ravel(); perm = npy(f['perm']).ravel(); C = npy(f['C']); V = npy(f['V']).ravel()
    n = len(gp); assert len(perm) == n == len(V) == len(C), m
    cnt = counts(f['cnt']); assert cnt.sum() == n, (m, cnt.sum(), n)
    pid_part = np.repeat(np.arange(len(cnt)), cnt)             # 分区序下的分区号
    gs = np.empty_like(gp); gs[perm] = gp                          # 候选映射：串行序梯度
    ps = np.empty_like(pid_part); ps[perm] = pid_part              # 串行序分区号
    D[m] = dict(g=gs, C=C, V=V, gp=gp, ps=ps, pid_id=pid_part)

# §2 分区界面异常检验
tests = {}
for m, d in D.items():
    C = d['C']; t = cKDTree(C); ib = np.where(inbox(C))[0]
    _, nb = t.query(C[ib], k=7); nb = nb[:, 1:]
    res = {}
    for lab, g, pid in (('candidate', d['g'], d['ps']), ('identity', d['gp'], d['pid_id'])):
        lg = np.log10(np.abs(g) + 1e-300); ok = np.abs(g[ib]) > 0
        dev = np.abs(lg[ib] - np.median(lg[nb], axis=1))
        iface = (pid[nb] != pid[ib][:, None]).any(axis=1)
        a, b = dev[ok & iface], dev[ok & ~iface]
        res[lab] = dict(n_iface=int(len(a)), n_interior=int(len(b)),
                        R1=float(np.percentile(a, 99) / np.percentile(b, 99)), R2=float(a.mean() / b.mean()))
    c, i = res['candidate'], res['identity']
    sens = (i['R1'] > 1.2) or (i['R2'] > 1.2)
    res['verdict'] = ('无灵敏度、不判' if not sens else ('离线未见错配' if (c['R1'] <= 1.2 and c['R2'] <= 1.2) else '离线疑有错配'))
    tests[m] = res
out['partition_interface_test'] = tests

# §0 κ（v2 盒、v3 盒、v1 全场）
kap = {}
for m, d in D.items():
    g, C = d['g'], d['C']; v2 = inbox(C)
    v3 = (C[:, 0] >= 8) & (C[:, 0] <= 48) & (np.abs(C[:, 1]) <= 12) & (C[:, 2] >= 0) & (C[:, 2] <= 12)
    kap[m] = {k: float(abs(g[s].sum()) / np.abs(g[s]).sum()) for k, s in (('v1', slice(None)), ('v2', v2), ('v3', v3))}
    kap[m].update(v2_sum=float(g[v2].sum()), v3_sum=float(g[v3].sum()), v1_sum=float(g.sum()))
out['kappa'] = kap
out['rel_change'] = {k: abs(kap['fine'][k + '_sum'] - kap['medium'][k + '_sum']) / abs(kap['fine'][k + '_sum']) for k in ('v1', 'v2', 'v3')}

# §3 近壁最强梯度单元相关
sets, trees, rho = [], {}, {}
for m, d in D.items():
    ib = np.where(inbox(d['C']))[0]; a = np.abs(d['g'][ib]); o = np.argsort(-a); cs = np.cumsum(a[o])
    k = int(np.searchsorted(cs, 0.9 * cs[-1]) + 1); sets.append(d['C'][ib[o[:k]]])
    trees[m] = cKDTree(d['C']); rho[m] = d['g'] / d['V']
P = np.vstack(sets)
samp, cover = {}, {}
for m, d in D.items():
    dist, idx = trees[m].query(P); samp[m] = rho[m][idx]
    ib = inbox(d['C']); u = np.unique(idx); u = u[ib[u]]
    cover[m] = dict(share_sum_abs_g_in_box=float(np.abs(d['g'][u]).sum() / np.abs(d['g'][ib]).sum()),
                    cells_hit_in_box=int(len(u)), median_dist=float(np.median(dist)), max_dist=float(dist.max()))
wd = wall_dist(P)
def stats(mask):
    a, b = samp['medium'][mask], samp['fine'][mask]
    return dict(n=int(mask.sum()), pearson=float(pearsonr(a, b)[0]), spearman=float(spearmanr(a, b)[0]),
                sign_agree=float(np.mean(np.sign(a) == np.sign(b))))
full, near = stats(np.ones(len(P), bool)), stats(wd <= 0.5)
out['nearwall'] = dict(points=int(len(P)), set_sizes=[int(len(s)) for s in sets], cover=cover, full=full, nearwall_le_0p5m=near,
                       condition2_pass=bool(full['pearson'] >= 0.8 and full['sign_agree'] >= 0.8 and near['pearson'] >= 0.8 and near['sign_agree'] >= 0.8))
json.dump(out, open(H + '/nearwall_numbers.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'inputs'}, ensure_ascii=False, indent=1))
