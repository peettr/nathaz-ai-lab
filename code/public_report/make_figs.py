"""L26.21 网站报告图：全部数字从回传结果文件读取。用法：python3 make_figs.py <报告figs目录>"""
import gzip, json, sys, tarfile, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('./Windows/Fonts/NotoSansSC-VF.ttf')
plt.rcParams['font.family'] = 'Noto Sans SC'; plt.rcParams['axes.unicode_minus'] = False
B = os.path.dirname(os.path.abspath(__file__)) + '/../G1'
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
def rows(path):
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt') as f: return [json.loads(l) for l in f if l.strip()]
def rel(a, fd): return abs(a - fd) / abs(fd) * 100
SRC = '数据来源：本线 DAFoam v5.1.1 计算（L26.21），中心差分为冷启动固定步数端点'
# 有限制器（1755645）
withL = rows(B + '/C2a/directional/returned_terminal_1755645/C2a_dir_0046_direction_rows.gz')
noL = rows(B + '/C2a/limiter/evidence_20261116/C2a_limiter_0037_direction_rows.gz')
def pick(R, kind, key, h):
    for r in R:
        if r.get('kind') == kind and r.get('direction' if kind == 'direction' else 'cell') == key and abs(r['h'] - h) < 1e-12:
            a = r.get('adjoint_dot', r.get('adjoint')); return a, r['fd']
    return None
# 随机方向多步长（1758199 端点）
ep = {r['label']: r['cp'] for r in rows(B + '/C2a/limiter_rand/returned/C2a_limiter_rand_0007_direction_endpoints.gz')}
a_rand_noL = pick(noL, 'direction', 'normal_seed2621', 1e-3)[0]
rand_noL = {1e-3: pick(noL, 'direction', 'normal_seed2621', 1e-3)[1]}
for h in (1e-2, 3e-3):
    rand_noL[h] = (ep[f'DIR_normal_seed2621_{h}_1'] - ep[f'DIR_normal_seed2621_{h}_-1']) / (2 * h)
ones_noL = {h: pick(noL, 'direction', 'all_ones', h) for h in (1e-3, 1e-2)}
# 立方体
tf = tarfile.open(B + '/cube/adj/evidence_1769537.tar.gz')
m = [x for x in tf.getmembers() if x.name.endswith('D_c2a_direction_rows.jsonl')][0]
cube = [json.loads(l) for l in tf.extractfile(m).read().decode().splitlines() if l.strip()]
cube = [r for r in cube if r.get('kind') == 'direction']
# NACA0012
naca = rows(B + '/C2a/diag_a_wallfn/third/returned_1756240/standard_0027_direction_rows.gz')
log = {}
# 图1
labels = ['全 1 方向', '随机方向', '单元 A', '单元 B']
keys = [('direction', 'all_ones'), ('direction', 'normal_seed2621'), ('cell_check', 140280), ('cell_check', 140281)]
e1 = [rel(*pick(withL, k, v, 1e-3)) for k, v in keys]; e2 = [rel(*pick(noL, k, v, 1e-3)) for k, v in keys]
log['fig1'] = dict(zip(labels, zip(e1, e2)))
fig, ax = plt.subplots(figsize=(7, 4.2)); x = range(4)
ax.bar([i - 0.2 for i in x], e1, 0.4, label='带 cellLimited 限制器', color='#c0504d')
ax.bar([i + 0.2 for i in x], e2, 0.4, label='去掉限制器', color='#4f81bd')
for i in x:
    ax.text(i - 0.2, e1[i] * 1.1, f'{e1[i]:.1f}%', ha='center', fontsize=8); ax.text(i + 0.2, e2[i] * 1.1, f'{e2[i]:.2f}%', ha='center', fontsize=8)
ax.axhline(1, ls='--', c='k', lw=1); ax.text(3.45, 1.1, '判据 1%', fontsize=8, ha='right')
ax.set_yscale('log'); ax.set_xticks(list(x)); ax.set_xticklabels(labels); ax.set_ylabel('伴随与中心差分相对差（%）')
ax.set_title('建筑算例（粗网格），步长 h=1e-3'); ax.legend(fontsize=8)
fig.text(0.01, 0.01, SRC, fontsize=6.5); fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out + '/fig1_limiter_effect.png', dpi=150); plt.close(fig)
# 图2 随机方向数值（符号）
a_w, f_w = pick(withL, 'direction', 'normal_seed2621', 1e-3); a_n, f_n = pick(noL, 'direction', 'normal_seed2621', 1e-3)
log['fig2'] = dict(with_adj=a_w, with_fd=f_w, no_adj=a_n, no_fd=f_n)
fig, ax = plt.subplots(figsize=(6.5, 4))
vals = [a_w * 1e4, f_w * 1e4, a_n * 1e4, f_n * 1e4]; cols = ['#c0504d', '#e6b9b8', '#4f81bd', '#b9cde5']
ax.bar(range(4), vals, color=cols); ax.axhline(0, c='k', lw=0.8)
ax.set_xticks(range(4)); ax.set_xticklabels(['伴随\n（带限制器）', '中心差分\n（带限制器）', '伴随\n（去限制器）', '中心差分\n（去限制器）'], fontsize=8)
for i, v in enumerate(vals): ax.text(i, v + (0.1 if v > 0 else -0.25), f'{v:+.2f}', ha='center', fontsize=8)
ax.set_ylabel('随机方向导数 ∇J·v（×1e-4）'); ax.set_title('随机方向：带限制器时符号相反，去掉后一致')
fig.text(0.01, 0.01, SRC, fontsize=6.5); fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out + '/fig2_random_sign.png', dpi=150); plt.close(fig)
# 图3 误差随步长
fig, ax = plt.subplots(figsize=(8, 4.2))
hs = sorted(rand_noL); eb = [rel(a_rand_noL, rand_noL[h]) for h in hs]
ax.plot(hs, eb, 'o-', c='#4f81bd', label='建筑·随机方向')
ho = sorted(ones_noL); ax.plot(ho, [rel(*ones_noL[h]) for h in ho], 's-', c='#1f497d', label='建筑·全 1 方向')
for d, mk, c, lb in (('normal_seed2621', 'o--', '#9bbb59', '立方体·随机方向'), ('ones', 's--', '#4e6128', '立方体·全 1 方向')):
    rr = sorted([r for r in cube if r['direction'] == d], key=lambda r: r['h'])
    ax.plot([r['h'] for r in rr], [rel(r['adjoint_dot'], r['fd']) for r in rr], mk, c=c, label=lb)
    log['fig3_cube_' + d] = [(r['h'], rel(r['adjoint_dot'], r['fd'])) for r in rr]
log['fig3_building_rand'] = list(zip(hs, eb)); log['fig3_building_ones'] = [(h, rel(*ones_noL[h])) for h in ho]
ax.axhline(1, ls='--', c='k', lw=1); ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('差分步长 h'); ax.set_ylabel('相对差（%）'); ax.set_title('去掉限制器后：各方向误差随步长'); ax.legend(fontsize=8, loc='center left', bbox_to_anchor=(1.01, 0.5))
fig.text(0.01, 0.01, SRC, fontsize=6.5); fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out + '/fig3_step_size.png', dpi=150); plt.close(fig)
# 图4 各算例汇总（h=1e-3）
def best_rand(R, key='direction', d='normal_seed2621'):
    return min(rel(r.get('adjoint_dot'), r['fd']) for r in R if r.get(key) == d)
cases = ['NACA0012 翼型\n（官方算例）', '建筑\n带限制器', '建筑\n去限制器', '立方体\n去限制器']
ones = [rel(*[(r['adjoint_dot'], r['fd']) for r in naca if r.get('direction') == 'all_ones' and abs(r['h'] - 1e-3) < 1e-12][0]),
        e1[0], e2[0], rel(*[(r['adjoint_dot'], r['fd']) for r in cube if r['direction'] == 'ones' and abs(r['h'] - 1e-3) < 1e-12][0])]
rnd = [rel(*[(r['adjoint_dot'], r['fd']) for r in naca if r.get('direction') == 'normal_seed2621' and abs(r['h'] - 1e-3) < 1e-12][0]),
       e1[1], e2[1], rel(*[(r['adjoint_dot'], r['fd']) for r in cube if r['direction'] == 'normal_seed2621' and abs(r['h'] - 1e-3) < 1e-12][0])]
log['fig4'] = dict(zip([c.replace('\n', '') for c in cases], zip(ones, rnd)))
fig, ax = plt.subplots(figsize=(7, 4.2)); x = range(4)
ax.bar([i - 0.2 for i in x], ones, 0.4, label='全 1 方向', color='#1f497d'); ax.bar([i + 0.2 for i in x], rnd, 0.4, label='随机方向', color='#9bbb59')
ax.axhline(1, ls='--', c='k', lw=1); ax.set_yscale('log'); ax.set_xticks(list(x)); ax.set_xticklabels(cases, fontsize=8)
ax.set_ylabel('相对差（%），h=1e-3'); ax.set_title('各算例伴随方向导数检验汇总'); ax.legend(fontsize=8)
fig.text(0.01, 0.01, SRC, fontsize=6.5); fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out + '/fig4_cases.png', dpi=150); plt.close(fig)
json.dump(log, open(os.path.dirname(os.path.abspath(__file__)) + '/fig_numbers.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(log, ensure_ascii=False, indent=1))
