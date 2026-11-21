"""
TMDI 风致随机响应：平稳情形完整范例（L22.6 T01 模板包，vibctrl-claude 10-21）

路线（Marian & Giaralis 2014 PEM 38:156-164 的状态空间 + Lyapunov + 参数优化思路，
此处把激励换成作用在结构上的 Kaimal 滤波风力）：
  1. 结构（塔筒一阶模态广义坐标 q）+ TMD 质量 x_d + 惯容（两端：TMD 质量 与 模态值 phi_b 的结构点）
  2. Kaimal 脉动风谱用二阶有理滤波器拟合，滤波器状态并入系统 -> 增广状态 X
  3. 代数 Lyapunov 方程 A P + P A^T + B W B^T = 0 求稳态协方差
  4. 以塔顶位移 RMS 为目标，对 TMD 频率比 nu 与阻尼比 zeta_d 寻优（给定质量比 mu、惯容比 beta）
  5. 自检：同一平稳问题的时域蒙特卡洛（精确离散化，Van Loan）与 Lyapunov 比较，误差应落在 MC 置信区间内；
     另用真实 Kaimal 谱做频域积分，量化滤波器拟合误差。
只含平稳情形。运行：python3 tmdi_stationary.py   （约 1 分钟，单核）
"""
import json, sys, time
import numpy as np
from scipy.linalg import solve_continuous_lyapunov, expm
from scipy.optimize import least_squares, minimize

# ---------------- 参数（来源见 01_推导.md 的参数来源表） ----------------
P = dict(
    M=437_000.0,      # 塔筒一阶前后模态的广义质量 [kg]（假设：RNA 350 t + 0.25×塔筒 347.46 t）
    f_s=0.32,         # 一阶前后频率 [Hz]（NREL 5 MW，卡 5NVCLN7I Table 2 p.3）
    zeta_s=0.01,      # 结构阻尼比（假设）
    kappa=1.225*200,  # 广义气动系数 rho*C_D*A_eff [kg/m]（假设：停机叶片+机舱+塔筒有效阻力面积 200 m^2）
    U=30.0,           # 轮毂高度平均风速 [m/s]（假设）
    I_u=0.12,         # 湍流强度（取值同卡 6EBHGKV3 p.17 的系综均值，作为示例）
    L_k=340.2,        # Kaimal 积分尺度参数 L = 8.1*Lambda, Lambda=42 m [m]（IEC 61400-1 形式，未建卡，待核）
    mu=0.01,          # TMD 质量比 m_d/M
    beta=0.05,        # 惯容比 b/M
    phi_b=0.5,        # 惯容下端所在高度的模态值（0 = 接地；1 = 接在塔顶，与 TMD 弹簧、阻尼器并联）
)

# ---------------- 1. Kaimal 谱与二阶滤波器拟合 ----------------
def kaimal_S(omega, U, I_u, L):
    """单边 Kaimal 谱，按角频率 omega [rad/s]：S_u(f)=4 s2 L/U /(1+6 f L/U)^(5/3)，S(omega)=S(f)/(2pi)"""
    s2 = (I_u*U)**2
    f = omega/(2*np.pi)
    return 4*s2*L/U / (1 + 6*f*L/U)**(5/3) / (2*np.pi)

def filt_S(omega, p):
    """二阶滤波器 H(s)=(c1 s + c0)/(s^2 + a1 s + a0) 在单位强度白噪声下的单边谱（单边白噪声谱高 1/pi）"""
    a0, a1, c0, c1 = np.exp(p)
    s = 1j*omega
    H = (c1*s + c0)/(s**2 + a1*s + a0)
    return np.abs(H)**2 / np.pi

def fit_filter(U, I_u, L, wmin=2*np.pi*1e-3, wmax=2*np.pi*5.0):
    w = np.logspace(np.log10(wmin), np.log10(wmax), 400)
    target = kaimal_S(w, U, I_u, L)
    s2 = (I_u*U)**2
    T = L/U
    S0 = target[0]                     # 低频端谱值；H(0)=c0/a0 满足 |H(0)|^2/pi = S0
    p0 = np.log([1/T**2, 2/T, np.sqrt(np.pi*S0)/T**2, 0.1*np.sqrt(np.pi*S0)/T])
    def res(p):
        return np.log(filt_S(w, p)) - np.log(target)
    sol = least_squares(res, p0, method='lm', max_nfev=20000)
    # 方差约束校验：滤波器输出方差（Lyapunov）与 sigma_u^2 比较
    return sol.x, w, target

def filter_ss(p):
    """可控标准型：xf' = Af xf + Bf w,  u = Cf xf；w 为单位强度白噪声 E[w(t)w(t')]=delta"""
    a0, a1, c0, c1 = np.exp(p)
    Af = np.array([[0.0, 1.0], [-a0, -a1]])
    Bf = np.array([[0.0], [1.0]])
    Cf = np.array([[c0, c1]])
    return Af, Bf, Cf

# ---------------- 2. 结构 + TMDI + 滤波器 的增广状态空间 ----------------
def build_system(P, nu, zeta_d, pfilt):
    M, ws = P['M'], 2*np.pi*P['f_s']
    K, C = M*ws**2, 2*P['zeta_s']*M*ws
    ca = P['kappa']*P['U']                  # 准定常气动阻尼 c_a = kappa*U
    md, b, phb = P['mu']*M, P['beta']*M, P['phi_b']
    # TMDI 有效质量 m_d + b，按其定义调谐频率
    wd = nu*ws
    kd = (md + b)*wd**2
    cd = 2*zeta_d*(md + b)*wd
    Mm = np.array([[M + b*phb**2, -b*phb], [-b*phb, md + b]])
    Cm = np.array([[C + ca + cd, -cd], [-cd, cd]])
    Km = np.array([[K + kd, -kd], [-kd, kd]])
    Minv = np.linalg.inv(Mm)
    Af, Bf, Cf = filter_ss(pfilt)
    # 状态 X = [q, x_d, q', x_d', xf1, xf2]
    A = np.zeros((6, 6))
    A[0:2, 2:4] = np.eye(2)
    A[2:4, 0:2] = -Minv @ Km
    A[2:4, 2:4] = -Minv @ Cm
    # 脉动风力 F = kappa*U*u 作用在 q 方程
    Fvec = np.array([[P['kappa']*P['U']], [0.0]])
    A[2:4, 4:6] = Minv @ Fvec @ Cf
    A[4:6, 4:6] = Af
    B = np.zeros((6, 1)); B[4:6, :] = Bf
    return A, B

def stationary_cov(A, B):
    """A P + P A^T + B B^T = 0（白噪声强度 1）"""
    return solve_continuous_lyapunov(A, -B @ B.T)

def responses(P, nu, zeta_d, pfilt):
    A, B = build_system(P, nu, zeta_d, pfilt)
    if np.max(np.linalg.eigvals(A).real) >= 0:
        return dict(sig_q=np.inf, sig_stroke=np.inf, sig_acc=np.inf)
    Pc = stationary_cov(A, B)
    sig_q = np.sqrt(Pc[0, 0])
    sig_stroke = np.sqrt(Pc[0, 0] + Pc[1, 1] - 2*Pc[0, 1])
    # 塔顶加速度方差：q'' = (A X)[2]，Var = (A P A^T + 0)[2,2]（白噪声不直接进 q''）
    sig_acc = np.sqrt((A @ Pc @ A.T)[2, 2])
    return dict(sig_q=sig_q, sig_stroke=sig_stroke, sig_acc=sig_acc, P=Pc, A=A, B=B)

# ---------------- 3. 参数优化（H2 / RMS） ----------------
def optimize(P, pfilt):
    def obj(z):
        nu, zd = np.exp(z)
        return responses(P, nu, zd, pfilt)['sig_q']
    best = None
    for nu0 in (0.8, 1.0, 1.2):
        for zd0 in (0.05, 0.15):
            r = minimize(obj, np.log([nu0, zd0]), method='Nelder-Mead',
                         options=dict(xatol=1e-6, fatol=1e-12, maxiter=4000))
            if best is None or r.fun < best.fun:
                best = r
    nu, zd = np.exp(best.x)
    return nu, zd, best.fun

def uncontrolled(P, pfilt):
    Q = dict(P); Q['mu'] = 1e-9; Q['beta'] = 0.0
    return responses(Q, 1.0, 0.05, pfilt)['sig_q']

# ---------------- 4. 频域核对（真实 Kaimal 谱 vs 滤波器） ----------------
def freq_domain_sigq(P, nu, zeta_d, spectrum):
    M, ws = P['M'], 2*np.pi*P['f_s']
    K, C = M*ws**2, 2*P['zeta_s']*M*ws
    ca = P['kappa']*P['U']
    md, b, phb = P['mu']*M, P['beta']*M, P['phi_b']
    wd = nu*ws; kd = (md+b)*wd**2; cd = 2*zeta_d*(md+b)*wd
    Mm = np.array([[M + b*phb**2, -b*phb], [-b*phb, md + b]])
    Cm = np.array([[C + ca + cd, -cd], [-cd, cd]])
    Km = np.array([[K + kd, -kd], [-kd, kd]])
    w = np.concatenate([np.linspace(1e-4, 0.2, 4000), np.linspace(0.2, 20, 60000)[1:]])
    Hq = np.empty_like(w, dtype=complex)
    for i, om in enumerate(w):
        Z = Km - om**2*Mm + 1j*om*Cm
        Hq[i] = np.linalg.solve(Z, np.array([1.0, 0.0]))[0]
    S_F = (P['kappa']*P['U'])**2 * spectrum(w)
    return np.sqrt(np.trapz(np.abs(Hq)**2*S_F, w))

# ---------------- 5. 时域蒙特卡洛（精确离散化） ----------------
def mc_check(A, B, dt=0.05, T=2400.0, burn=600.0, n_traj=300, seed=20261021):
    n = A.shape[0]
    # Van Loan：离散转移 Phi 与过程噪声协方差 Qd
    Z = np.zeros((2*n, 2*n))
    Z[:n, :n] = -A; Z[:n, n:] = B @ B.T; Z[n:, n:] = A.T
    E = expm(Z*dt)
    Phi = E[n:, n:].T
    Qd = Phi @ E[:n, n:]
    Qd = 0.5*(Qd + Qd.T)
    Lc = np.linalg.cholesky(Qd + 1e-30*np.eye(n))
    rng = np.random.default_rng(seed)
    X = np.zeros((n, n_traj))
    nb, nt = int(burn/dt), int(T/dt)
    acc_q = np.zeros(n_traj)
    for k in range(nb + nt):
        X = Phi @ X + Lc @ rng.standard_normal((n, n_traj))
        if k >= nb:
            acc_q += X[0]**2
    var_traj = acc_q/nt                     # 每条样本的时间平均方差
    m = var_traj.mean(); se = var_traj.std(ddof=1)/np.sqrt(n_traj)
    return m, se, var_traj

def main():
    t0 = time.time()
    pfilt, w, target = fit_filter(P['U'], P['I_u'], P['L_k'])
    Af, Bf, Cf = filter_ss(pfilt)
    Pf = solve_continuous_lyapunov(Af, -Bf @ Bf.T)
    var_filter = float((Cf @ Pf @ Cf.T)[0, 0]); var_true = (P['I_u']*P['U'])**2
    fit_err = np.max(np.abs(np.log(filt_S(w, pfilt)/target)))

    sq0 = uncontrolled(P, pfilt)
    nu, zd, sq = optimize(P, pfilt)
    r = responses(P, nu, zd, pfilt)

    # 频域：真实 Kaimal 与滤波器谱
    sq_fd_kaimal = freq_domain_sigq(P, nu, zd, lambda om: kaimal_S(om, P['U'], P['I_u'], P['L_k']))
    sq_fd_filter = freq_domain_sigq(P, nu, zd, lambda om: filt_S(om, pfilt))

    # MC 检验
    m, se, _ = mc_check(r['A'], r['B'])
    var_lyap = r['P'][0, 0]
    z = (m - var_lyap)/se

    out = dict(
        params=P, filter_params_log=pfilt.tolist(),
        filter_variance_vs_true=[var_filter, var_true],
        filter_fit_max_abs_log_error_0p001_5Hz=float(fit_err),
        sigma_q_uncontrolled_m=float(sq0),
        optimum=dict(nu=float(nu), zeta_d=float(zd), sigma_q_m=float(sq),
                     reduction_pct=float(100*(1 - sq/sq0)),
                     sigma_stroke_m=float(r['sig_stroke']), sigma_acc_ms2=float(r['sig_acc'])),
        freq_domain_check=dict(sigma_q_filter=float(sq_fd_filter), sigma_q_true_kaimal=float(sq_fd_kaimal),
                               lyapunov_vs_filterFD_rel=float(sq/sq_fd_filter - 1),
                               filter_vs_trueKaimal_rel=float(sq_fd_filter/sq_fd_kaimal - 1)),
        mc_check=dict(var_mc=float(m), se_mc=float(se), var_lyapunov=float(var_lyap),
                      z_score=float(z), within_95CI=bool(abs(z) < 1.96),
                      setup='300 条样本 × 2400 s（另弃 600 s），dt=0.05 s，Van Loan 精确离散'),
        runtime_s=round(time.time() - t0, 1),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open(sys.argv[1] if len(sys.argv) > 1 else 'check_result.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
