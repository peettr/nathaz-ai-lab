"""L26.10 L1 checker: L26.6 checklist items applicable to the 2D square cylinder.

Written from the checklist text (06_Logs/L26.6/CFD静默错误检查清单.md) and the
physical task spec below, before the injection manifest is frozen.
Compares readbacks with the TASK SPEC (independent of the run's case.json).

Usage: python l1_check.py <run_dir> <A|B> [--steps 200]  -> prints JSON
Exit 0 always; verdict in JSON: l1 = 'pass' | 'block', l2 = 'pass' | 'block'.
"""
import ast
import json
import math
import re
import sys
from pathlib import Path

NU = 1.0 / 22000.0
SPEC = {
    'A': {'time': 'unsteady-2nd-order', 'dt': 0.05, 'cells': 9600, 'nodes': 9760},
    'B': {'time_contains': 'bounded', 'dt': 0.025, 'crit': 1e-5},
}
REL = 1e-6


def close(a, b, rel=REL):
    try:
        return abs(float(a) - float(b)) <= rel * max(1.0, abs(float(b)))
    except Exception:
        return False


def marks(log):
    out = {}
    for line in log.splitlines():
        m = re.match(r'^([A-Z][A-Z0-9_]+) (.*)$', line)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def lit(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        return None


def series(path, name):
    """Return the report column `name` from a Fluent .out file."""
    if not path.exists():
        return []
    col, vals = None, []
    for line in path.read_text(errors='replace').splitlines():
        if line.startswith('(') and '"' in line:
            heads = re.findall(r'"([^"]+)"', line)
            if name in heads:
                col = heads.index(name)
            continue
        parts = line.split()
        try:
            nums = [float(x) for x in parts]
        except ValueError:
            continue
        if not nums:
            continue
        idx = col if col is not None and col < len(nums) else 1
        if idx < len(nums):
            vals.append(nums[idx])
    return vals


def residual_steps(log):
    """Per time step final residuals from the Fluent console (same idea as T28 diag_readonly)."""
    cols, steps, cur, last = None, [], [], None
    for line in log.splitlines():
        h = re.match(r'^\s*iter\s+(.*?)\s+time/iter', line)
        if h:
            cols = h.group(1).split(); continue
        if line.startswith('Updating solution at time levels'):
            if cur: steps.append(cur)
            cur = []; continue
        r = re.match(r'^\s*(\d+)\s+((?:[0-9.]+e[+-]\d+\s+)+)', line)
        if r and cols:
            it = int(r.group(1))
            if it == last: continue
            last = it
            cur.append(dict(zip(cols, [float(x) for x in r.group(2).split()[:len(cols)]])))
    if cur: steps.append(cur)
    return steps


def check(run_dir, kind, steps=200):
    d = Path(run_dir)
    log = (d / 'run.log').read_text(errors='replace') if (d / 'run.log').exists() else ''
    mk = marks(log)
    au = lit(mk['L2610_AUDIT'][-1]) if 'L2610_AUDIT' in mk else None
    sp = SPEC[kind]
    r = {}

    def put(k, ok, why=''):
        r[k] = {'ok': bool(ok), 'why': why}

    if not isinstance(au, dict):
        put('K01_audit_present', False, 'no L2610_AUDIT')
        au = {}
    visc = au.get('viscous') or {}
    put('K01_model', isinstance(visc, dict) and visc.get('model') == 'k-omega' and visc.get('k_omega_model') == 'sst', repr(visc)[:80] if not isinstance(visc, dict) else f"{visc.get('model')}/{visc.get('k_omega_model')}")
    t = au.get('time')
    if kind == 'A':
        put('K01_time', t == sp['time'], repr(t))
    else:
        put('K01_time', isinstance(t, str) and sp['time_contains'] in t.lower(), repr(t))
    put('K01_density', close(au.get('air_density'), 1.0), repr(au.get('air_density')))
    put('K01_viscosity', close(au.get('air_viscosity'), NU), repr(au.get('air_viscosity')))
    ref = au.get('reference') or {}
    want = {'area': 1.0, 'length': 1.0, 'velocity': 1.0, 'density': 1.0, 'viscosity': NU, 'depth': 1.0}
    bad = [k for k, v in want.items() if not (isinstance(ref, dict) and close(ref.get(k), v))]
    put('K01_reference', not bad, 'bad ' + ','.join(bad) if bad else '')
    # dt: harness A sets dt after the audit (same order as T28 solver_run), so use DT_READBACK when present.
    dt = lit(mk['DT_READBACK'][-1]) if 'DT_READBACK' in mk else au.get('dt')
    put('K01_dt', close(dt, sp['dt']), repr(dt))
    # K02 inlet: direction cosine >= 0.99 (a) and magnitude within 1% of spec flow (b)
    meth = au.get('inlet_method')
    comps = au.get('inlet_components')
    u = v = None
    if meth == 'Components' and isinstance(comps, list) and len(comps) >= 2:
        try:
            u, v = float(comps[0]['value']), float(comps[1]['value'])
        except Exception:
            pass
    if u is None:
        put('K02a_inlet_direction', False, f'method={meth!r} not uniform Cartesian components')
        put('K02b_inlet_flow', False, 'components unreadable')
    else:
        mag = math.hypot(u, v)
        put('K02a_inlet_direction', mag > 0 and u / mag >= 0.99, f'cos={u / mag if mag else 0:.5f}')
        put('K02b_inlet_flow', abs(u - 1.0) <= 0.01, f'u={u:.6g}')
        put('K01_inlet_exact', close(u, 1.0) and close(v, 0.0), f'u={u!r} v={v!r}')
    # K08b-like / residual request (B only)
    if kind == 'B':
        ct = au.get('criterion_type')
        eqs = au.get('residual_equations') or {}
        crits = [st.get('absolute_criteria') for st in eqs.values() if isinstance(st, dict) and st.get('monitor', False)]
        put('K01_criterion', ct == 'absolute' and crits and all(close(c, sp['crit']) for c in crits), f'{ct} {crits}')
        st = residual_steps(log)
        if st:
            conv = sum(1 for s in st if s and max(s[-1].values()) <= sp['crit'] * 1.0001) / len(st)
            put('K08b_inner_converged', conv >= 0.9, f'fraction of steps reaching {sp["crit"]}: {conv:.2f} (n={len(st)})')
        else:
            put('K08b_inner_converged', False, 'no residual rows parsed')
    # K09 mesh (A only): size matches requested coarse grid, min volume > 0
    if kind == 'A':
        trn = d / 'out' / 'mesh_size.trn'
        txt = trn.read_text(errors='replace') if trn.exists() else ''
        m = re.search(r'^\s*0\s+(\d+)\s+(\d+)\s+(\d+)', txt, re.M)
        if m:
            cells, nodes = int(m.group(1)), int(m.group(3))
            put('K09_mesh_size', cells == sp['cells'] and nodes == sp['nodes'], f'cells={cells} nodes={nodes}')
        else:
            put('K09_mesh_size', False, 'size-info unreadable')
        mc = (d / 'out' / 'mesh_check.trn')
        mtxt = mc.read_text(errors='replace') if mc.exists() else ''
        vols = re.findall(r'minimum volume\s*\([^)]*\)\s*:\s*([+-]?[\d.eE+-]+)', mtxt, re.I)
        put('K09_min_volume', bool(vols) and all(float(x) > 0 for x in vols), f'{vols[:1]}')
    # K08a / K17b outputs
    cd = series(d / 'out' / 'cd.out', 'cd')
    put('K17b_solve_completed', 'SOLVE_RETURNED' in mk and len(cd) >= steps and 'RUN_EXCEPTION' not in mk,
        f'returned={"SOLVE_RETURNED" in mk} cd_rows={len(cd)}')
    cdm = sum(cd[-20:]) / len(cd[-20:]) if len(cd) >= 20 else None
    put('K08a_cd_magnitude', cdm is not None and 0.5 * 2.22 <= cdm <= 2.0 * 2.22, f'cd_mean_last20={cdm}')
    l1 = 'pass' if all(x['ok'] for x in r.values()) else 'block'
    l2 = 'pass' if (cdm is not None and 1.0 <= cdm <= 3.0) else 'block'
    l0 = 'block' if 'L0_BLOCK' in mk else 'pass'
    return {'run': d.name, 'kind': kind, 'l0': l0, 'l0_detail': mk.get('L0_BLOCK', []),
            'l1': l1, 'l1_failed': [k for k, x in r.items() if not x['ok']], 'l2': l2,
            'cd_mean_last20': cdm, 'checks': r}


if __name__ == '__main__':
    steps = 200
    if '--steps' in sys.argv:
        steps = int(sys.argv[sys.argv.index('--steps') + 1])
    print(json.dumps(check(sys.argv[1], sys.argv[2], steps), ensure_ascii=False, indent=1))
