"""
含光滑幂律黏滞阻尼器的 TMDI 在 Kaimal 滤波风荷载下的统计线性化（L22.6 T02 模板包，vibctrl-claude 11-27）

路线：
  1. 结构（塔筒一阶模态广义坐标 q）+ TMD 质量 x_d + 惯容 b（两端：TMD 质量与模态值 phi_b 的结构点，线性）
  2. TMD 与塔顶之间的阻尼器为幂律黏滞：F_d = c_a * |v|^alpha * sgn(v)，v = x_d' - q'（唯一的非线性）
  3. Kaimal 脉动风谱用二阶有理滤波器拟合，滤波器状态并入系统（同 T01）
  4. 统计线性化（高斯假设）：F_d ≈ c_eq v，c_eq = E[dF/dv] = E[vF]/E[v^2]
       = c_a * sigma_v^(alpha-1) * 2^((alpha+1)/2) * Gamma(alpha/2+1)/sqrt(pi)
     c_eq 依赖 sigma_v，sigma_v 由等效线性系统的 Lyapunov 方程给出 -> 不动点迭代
  5. 以塔顶位移 RMS 为目标，对频率比 nu 与幂律系数 c_a 寻优（给定 mu、beta、phi_b、alpha）
  6. 自检：
     C1 alpha=1 退化：SL 必须与线性 Lyapunov 一致；同一非线性积分器的 MC 与 Lyapunov 一致（|z|<1.96）
     C2 alpha=0.5 最优点：SL 预测 sigma_q 与非线性时域 MC 的相对差 <= 5%（SL 是近似，判据开跑前写定）
运行：python3 tmdi_powerlaw_sl.py [输出 json]（单核约 1–3 分钟，依赖 numpy、scipy）
"""
import json, sys, time
import numpy as np
from scipy.linalg import solve_continuous_lyapunov, expm
from scipy.optimize import least_squares, minimize
from scipy.special import gamma as Gfun

P = dict(
    M=437_000.0, f_s=0.32, zeta_s=0.01, kappa=1.225*200, U=30.0, I_u=0.12, L_k=340.2,
    mu=0.01, beta=0.05, phi_b=0.5,
    alpha=0.5,        # 幂律指数（示例值，假设；常见黏滞阻尼器 0.3–1）
)

# ---------- Kaimal 与滤波器（同 T01） ----------
def kaimal_S(omega, U, I_u, L):
    s2 = (I_u*U)**2; f = omega/(2*np.pi)
    return 4*s2*L/U/(1 + 6*f*L/U)**(5/3)/(2*np.pi)

def filt_S(omega, p):
    a0, a1, c0, c1 = np.exp(p); s = 1j*omega
    return np.abs((c1*s + c0)/(s**2 + a1*s + a0))**2/np.pi

def fit_filter(U, I_u, L):
    w = np.logspace(np.log10(2*np.pi*1e-3), np.log10(2*np.pi*5.0), 400)
    target = kaimal_S(w, U, I_u, L); T = L/U; S0 = target[0]
    p0 = np.log([1/T**2, 2/T, np.sqrt(np.pi*S0)/T**2, 0.1*np.sqrt(np.pi*S0)/T])
    sol = least_squares(lambda p: np.log(filt_S(w, p)) - np.log(target), p0, method='lm', max_nfev=20000)
    return sol.x

def filter_ss(p):
    a0, a1, c0, c1 = np.exp(p)
    return np.array([[0.0, 1.0], [-a0, -a1]]), np.array([[0.0], [1.0]]), np.array([[c0, c1]])

# ---------- 结构矩阵（阻尼器单独拿出） ----------
def mats(P, nu):
    M, ws = P['M'], 2*np.pi*P['f_s']
    K, C = M*ws**2, 2*P['zeta_s']*M*ws
    ca = P['kappa']*P['U']
    md, b, phb = P['mu']*M, P['beta']*M, P['phi_b']
    kd = (md + b)*(nu*ws)**2
    Mm = np.array([[M + b*phb**2, -b*phb], [-b*phb, md + b]])
    C0 = np.array([[C + ca, 0.0], [0.0, 0.0]])          # 不含 TMD 阻尼器
    Km = np.array([[K + kd, -kd], [-kd, kd]])
    e = np.array([-1.0, 1.0])                            # v = e·x' = x_d' - q'
    f = np.array([P['kappa']*P['U'], 0.0])
    return Mm, C0, Km, e, f

def build_linear(P, nu, ceq, pfilt):
    Mm, C0, Km, e, f = mats(P, nu)
    Cm = C0 + ceq*np.outer(e, e)
    Minv = np.linalg.inv(Mm); Af, Bf, Cf = filter_ss(pfilt)
    A = np.zeros((6, 6)); A[0:2, 2:4] = np.eye(2)
    A[2:4, 0:2] = -Minv @ Km; A[2:4, 2:4] = -Minv @ Cm
    A[2:4, 4:6] = Minv @ f[:, None] @ Cf; A[4:6, 4:6] = Af
    B = np.zeros((6, 1)); B[4:6, :] = Bf
    return A, B

def lyap(A, B):
    if np.max(np.linalg.eigvals(A).real) >= 0:
        return None
    return solve_continuous_lyapunov(A, -B @ B.T)

def kfac(alpha):
    return 2**((alpha + 1)/2)*Gfun(alpha/2 + 1)/np.sqrt(np.pi)

def sigma_v(Pc):
    # v = x_d' - q' -> 状态 3、2
    return np.sqrt(Pc[3, 3] + Pc[2, 2] - 2*Pc[2, 3])

def stat_lin(P, nu, c_a, pfilt, ceq0=None, tol=1e-12, itmax=500):
    """不动点：ceq <- c_a sigma_v(ceq)^(alpha-1) kfac；对数域松弛 0.5"""
    al = P['alpha']; k = kfac(al)
    ceq = c_a if ceq0 is None else ceq0
    for it in range(itmax):
        A, B = build_linear(P, nu, ceq, pfilt); Pc = lyap(A, B)
        if Pc is None:
            return None
        new = c_a*sigma_v(Pc)**(al - 1)*k
        if abs(np.log(new/ceq)) < tol:
            ceq = new; break
        ceq = np.exp(0.5*np.log(ceq) + 0.5*np.log(new))
    A, B = build_linear(P, nu, ceq, pfilt); Pc = lyap(A, B)
    return dict(ceq=ceq, P=Pc, A=A, B=B, iters=it + 1, sig_q=np.sqrt(Pc[0, 0]), sig_v=sigma_v(Pc),
                sig_stroke=np.sqrt(Pc[0, 0] + Pc[1, 1] - 2*Pc[0, 1]))

def optimize(P, pfilt, x0):
    def obj(z):
        r = stat_lin(P, np.exp(z[0]), np.exp(z[1]), pfilt)
        return np.inf if r is None else r['sig_q']
    best = None
    for dz in ([0, 0], [0.1, 1.0], [-0.1, -1.0]):
        r = minimize(obj, np.array(x0) + dz, method='Nelder-Mead', options=dict(xatol=1e-7, fatol=1e-14, maxiter=3000))
        if best is None or r.fun < best.fun:
            best = r
    return np.exp(best.x), best.fun

# ---------- 非线性时域 MC ----------
def mc_nonlinear(P, nu, c_a, pfilt, dt=0.01, T=1800.0, burn=300.0, n_traj=200, seed=20261127):
    Mm, C0, Km, e, f = mats(P, nu); Minv = np.linalg.inv(Mm); al = P['alpha']
    Af, Bf, Cf = filter_ss(pfilt)
    # 滤波器精确离散（Van Loan）
    n = 2; Z = np.zeros((4, 4)); Z[:2, :2] = -Af; Z[:2, 2:] = Bf @ Bf.T; Z[2:, 2:] = Af.T
    E = expm(Z*dt); Phi = E[2:, 2:].T; Qd = Phi @ E[:2, 2:]; Lc = np.linalg.cholesky(0.5*(Qd + Qd.T))
    rng = np.random.default_rng(seed)
    xf = np.linalg.cholesky(solve_continuous_lyapunov(Af, -Bf @ Bf.T)) @ rng.standard_normal((2, n_traj))
    x = np.zeros((2, n_traj)); v = np.zeros((2, n_traj))
    def acc(x, v, u):
        vr = e @ v
        Fd = c_a*np.abs(vr)**al*np.sign(vr)
        return Minv @ (f[:, None]*u - C0 @ v - Km @ x - np.outer(e, Fd))
    nb, nt = int(burn/dt), int(T/dt)
    sq = np.zeros(n_traj); sv = np.zeros(n_traj); m4 = np.zeros(n_traj)
    u0 = (Cf @ xf)[0]
    for k in range(nb + nt):
        xf = Phi @ xf + Lc @ rng.standard_normal((2, n_traj)); u1 = (Cf @ xf)[0]; um = 0.5*(u0 + u1)
        k1x, k1v = v, acc(x, v, u0)
        k2x, k2v = v + 0.5*dt*k1v, acc(x + 0.5*dt*k1x, v + 0.5*dt*k1v, um)
        k3x, k3v = v + 0.5*dt*k2v, acc(x + 0.5*dt*k2x, v + 0.5*dt*k2v, um)
        k4x, k4v = v + dt*k3v, acc(x + dt*k3x, v + dt*k3v, u1)
        x = x + dt/6*(k1x + 2*k2x + 2*k3x + k4x); v = v + dt/6*(k1v + 2*k2v + 2*k3v + k4v); u0 = u1
        if k >= nb:
            sq += x[0]**2; vr = e @ v; sv += vr**2; m4 += vr**4
    var_q = sq/nt; var_v = sv/nt
    m = var_q.mean(); se = var_q.std(ddof=1)/np.sqrt(n_traj)
    kurt = (m4/nt).mean()/var_v.mean()**2
    return dict(var_q=float(m), se=float(se), sigma_q=float(np.sqrt(m)), sigma_v=float(np.sqrt(var_v.mean())),
                kurtosis_v=float(kurt), setup=f'{n_traj} 条样本 × {T:.0f} s（另弃 {burn:.0f} s），dt={dt} s，结构 RK4、滤波器 Van Loan 精确离散')

def main():
    t0 = time.time()
    pfilt = fit_filter(P['U'], P['I_u'], P['L_k'])
    # 线性 TMDI 最优（alpha=1）作起点与对照
    PL = dict(P); PL['alpha'] = 1.0
    M, ws = P['M'], 2*np.pi*P['f_s']; mdb = (P['mu'] + P['beta'])*M
    (nuL, cL), sqL = optimize(PL, pfilt, np.log([0.98, 2*0.07*mdb*0.98*ws]))
    # 无控
    Q = dict(PL); Q['mu'] = 1e-9; Q['beta'] = 0.0
    sq0 = stat_lin(Q, 1.0, 1e-6, pfilt)['sig_q']
    # C1：alpha=1 退化检查
    rL = stat_lin(PL, nuL, cL, pfilt)
    A, B = build_linear(PL, nuL, cL, pfilt); var_lyap = lyap(A, B)[0, 0]
    c1_sl_rel = abs(rL['sig_q']**2/var_lyap - 1)
    mcL = mc_nonlinear(PL, nuL, cL, pfilt); zL = (mcL['var_q'] - var_lyap)/mcL['se']
    # 幂律最优
    sv_lin = rL['sig_v']; ca0 = cL*sv_lin**(1 - P['alpha'])/kfac(P['alpha'])
    (nuN, cN), sqN = optimize(P, pfilt, np.log([nuL, ca0]))
    rN = stat_lin(P, nuN, cN, pfilt)
    mcN = mc_nonlinear(P, nuN, cN, pfilt)
    relN = rN['sig_q']/mcN['sigma_q'] - 1
    rel_se = mcN['se']/(2*mcN['var_q'])
    out = dict(
        params=P, filter_params_log=pfilt.tolist(), sigma_q_uncontrolled_m=float(sq0),
        linear_TMDI_optimum=dict(nu=float(nuL), c_d=float(cL), sigma_q_m=float(sqL), reduction_pct=float(100*(1 - sqL/sq0))),
        powerlaw_SL_optimum=dict(alpha=P['alpha'], nu=float(nuN), c_alpha=float(cN), c_eq=float(rN['ceq']),
                                 sigma_v=float(rN['sig_v']), sigma_q_m=float(rN['sig_q']), sigma_stroke_m=float(rN['sig_stroke']),
                                 reduction_pct=float(100*(1 - rN['sig_q']/sq0)), sl_iterations=int(rN['iters'])),
        check_C1_alpha1=dict(sl_vs_lyapunov_rel=float(c1_sl_rel), var_lyapunov=float(var_lyap), var_mc=mcL['var_q'], se_mc=mcL['se'],
                             z_score=float(zL), pass_=bool(c1_sl_rel < 1e-10 and abs(zL) < 1.96), setup=mcL['setup']),
        check_C2_alpha=dict(sigma_q_SL=float(rN['sig_q']), sigma_q_MC=mcN['sigma_q'], rel_SL_vs_MC=float(relN),
                            mc_rel_se_sigma=float(rel_se), sigma_v_SL=float(rN['sig_v']), sigma_v_MC=mcN['sigma_v'],
                            kurtosis_v_MC=mcN['kurtosis_v'], criterion='|sigma_SL/sigma_MC - 1| <= 0.05（开跑前写定）',
                            pass_=bool(abs(relN) <= 0.05), setup=mcN['setup']),
        runtime_s=round(time.time() - t0, 1),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    with open(sys.argv[1] if len(sys.argv) > 1 else 'check_result.json', 'w', encoding='utf-8') as fo:
        json.dump(out, fo, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
