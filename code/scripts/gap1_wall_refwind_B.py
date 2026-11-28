"""L22.10 缺口①B（11-27，方案增补写定）：幂律换算墙面代表高度的来流，重标 SH12 墙面/楼板底 χ²/χ²_V。
四档探头（推断高度，模型 m）z=0.368/0.582/0.734/0.886，U=18.72/20.69/21.51/21.97 m/s，Iu=0.133/0.108/0.090/0.080；
拟合 U∝z^α、Iu∝z^β。χ²=S_F·U²/(4F̄²S_u)，谱形不变时 S_u∝(Iu·U)²，故换到 z_w 后 χ²_w = χ²_屋面 × (Iu_屋面/Iu_w)²（U² 抵消）。
代表高度：墙面中高 17 ft（主），敏感性 12 ft（楼板）与 22 ft（檐口）；楼板底取 12 ft。f* 轴不变（仍按屋面 H、U 定义，便于与原表对照）。
输入 m3_q3_walls_prj.json；输出表（件中位比，f*=0.1–1.2）。"""
import json, sys
import numpy as np
Q = json.load(open(sys.argv[1])); FG = np.array(Q['fstar_grid'])
z = np.array([12.08, 19.08, 24.08, 29.08]) * 0.03048; U = np.array([18.72, 20.69, 21.51, 21.97]); I = np.array([.133, .108, .090, .080])
a = np.polyfit(np.log(z), np.log(U), 1); b = np.polyfit(np.log(z), np.log(I), 1)
Iu = lambda ft: float(np.exp(np.polyval(b, np.log(ft * 0.03048))))
Ir = 0.0900984  # A25SH12 探头实测 Iu
print('拟合 α=%.3f β=%.3f；Iu(12 ft)=%.3f Iu(17 ft)=%.3f Iu(22 ft)=%.3f；屋面探头 Iu=%.4f' % (a[0], b[0], Iu(12), Iu(17), Iu(22), Ir))
fac = {ft: (Ir / Iu(ft)) ** 2 for ft in (12, 17, 22)}
print('缩放因子 (Iu_屋面/Iu_w)²：', {k: round(v, 3) for k, v in fac.items()})
pts = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]; ix = [int(np.argmin(abs(FG - p))) for p in pts]
L = [v for k, v in Q['cases'].items() if k.startswith('A20SH12')]
print('SH12 件中位 χ²/χ²_V，f*=', pts)
for key, fts in [('windward|whole', (17, 12, 22)), ('windward|2.0', (17, 12, 22)), ('windward|4.0', (17, 12, 22)), ('side_L|whole', (17, 12, 22)), ('side_R|whole', (17, 12, 22)), ('gable|whole', (17, 12, 22)), ('floor|whole', (12,)), ('floor|2.0', (12,))]:
    r = np.array([[np.nan if x is None else x for x in v[key]['ratio_med']] for v in L], float)[:, ix]
    with np.errstate(all='ignore'): med = np.nanmedian(r, 0)
    s = '  '.join('%5.2f' % x for x in med)
    print(f'{key:16s} 原（屋面参照） {s} | 范围 {np.nanmin(med):.2f}–{np.nanmax(med):.2f}')
    for ft in fts:
        m2 = med * fac[ft]; print(f'{"":16s} 换到 {ft} ft     ' + '  '.join('%5.2f' % x for x in m2) + f' | 范围 {np.nanmin(m2):.2f}–{np.nanmax(m2):.2f}')
