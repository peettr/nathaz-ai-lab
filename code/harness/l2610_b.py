"""L26.10 baseline B harness (restart, mirrors T28 converged_segment.main).

Every line between source read and solve is converged_segment.py (sha 5e9c4a09)
with two injection points:
  --crit         absolute residual criterion written (T28 value 1e-5)   [M3, S2]
  --time-filter  'correct' = T28 filter; 'buggy' = F07-type filter that only
                 looks for "2nd"/"second" and so may pick plain 2nd order [M4, S1]
Its RuntimeError raises are L0; observe mode prints L0_BLOCK and continues.
"""
import argparse
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from l2610_common import mark, sha, start_solver, audit  # noqa: E402


def l0(cond, msg):
    if cond:
        mark('L0_BLOCK', ('converged_segment', msg))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--dt', type=float, default=0.025)
    p.add_argument('--steps', type=int, default=200)
    p.add_argument('--crit', type=float, default=1e-5)
    p.add_argument('--time-filter', choices=('correct', 'buggy'), default='correct')
    a = p.parse_args()
    mark('INJ', {'crit': a.crit, 'time_filter': a.time_filter})
    src = a.source.resolve()
    dat = src.with_name(src.name.replace('.cas.h5', '.dat.h5'))
    root = a.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for f in (src, dat):
        mark('SOURCE_SHA256', (str(f), sha(f)))
    session = None
    try:
        session = start_solver(1)
        mark('FLUENT_VERSION', session.get_fluent_version())
        session.settings.file.read_case_data(file_name=str(src))
        s = session.settings
        mark('FLOW_TIME_START', s.solution.run_calculation.transient_controls.flow_time.get_state())
        visc = s.setup.models.viscous.get_state()
        l0(visc.get('model') != 'k-omega' or visc.get('k_omega_model') != 'sst', 'source is not SST')
        required = {'mom', 'k', 'omega'}
        scheme = s.solution.methods.p_v_coupling.flow_scheme
        l0('Coupled' not in scheme.allowed_values(), 'Coupled not offered')
        scheme.set_state('Coupled')
        time = s.setup.general.solver.time
        allowed = time.allowed_values()
        mark('TIME_ALLOWED', allowed)
        if a.time_filter == 'correct':
            bounded = [v for v in allowed if 'bounded' in v.lower() and ('2nd' in v.lower() or 'second' in v.lower())]
        else:
            bounded = [v for v in allowed if '2nd' in v.lower() or 'second' in v.lower()]
        l0(not bounded, 'bounded second-order implicit unavailable')
        if bounded:
            time.set_state(bounded[0])
        mark('TIME_READBACK', time.get_state())
        spatial = s.solution.methods.spatial_discretization.discretization_scheme
        names = spatial.get_object_names()
        l0(not required.issubset(set(names)), 'unexpected spatial schemes: ' + repr(names))
        for n in required & set(names):
            leaf = spatial[n]
            l0('second-order-upwind' not in leaf.allowed_values(), 'second order unavailable for ' + n)
            leaf.set_state('second-order-upwind')
        residual = s.solution.monitor.residual
        l0('absolute' not in residual.options.criterion_type.allowed_values(), 'absolute criterion unavailable')
        residual.options.criterion_type.set_state('absolute')
        for name in residual.equations.get_object_names():
            eq = residual.equations[name]
            if eq.get_state().get('monitor', False):
                eq.absolute_criteria = a.crit
                eq.check_convergence = True
        reports = s.solution.monitor.report_files
        for name in ('cd', 'cl'):
            l0(name not in reports.get_object_names(), 'missing ' + name + ' report definition')
            reports[name].file_name = str(root / (name + '.out'))
        controls = s.solution.run_calculation.transient_controls
        controls.time_step_size = a.dt
        l0(controls.time_step_size.get_state() != a.dt, 'dt readback mismatch')
        audit(session)
        s.solution.run_calculation.dual_time_iterate(time_step_count=a.steps, max_iter_per_step=50)
        mark('SOLVE_RETURNED', a.steps)
    except BaseException as exc:
        traceback.print_exc()
        mark('RUN_EXCEPTION', repr(exc)[:300])
    finally:
        try:
            if session is not None:
                session.exit()
        except Exception as exc:
            mark('EXIT_ERROR', repr(exc)[:200])
        mark('SESSION_CLOSED', True)


if __name__ == '__main__':
    main()
