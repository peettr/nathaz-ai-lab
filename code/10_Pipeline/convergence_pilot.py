"""SST restart pilot: read back numerics and preserve source case/data."""
import argparse
import hashlib
import json
import traceback
from pathlib import Path
from launch import start, close

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--dt', required=True, type=float)
    p.add_argument('--steps', required=True, type=int)
    p.add_argument('--cores', default=8, type=int)
    a = p.parse_args()
    root = a.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    src = a.source.resolve()
    dat = src.with_name(src.name.replace('.cas.h5', '.dat.h5'))
    if not src.name.endswith('.cas.h5') or not src.is_file() or not dat.is_file():
        raise ValueError('complete cas/dat pair required')
    for f in (src, dat): print('SOURCE_SHA256', f, sha(f), flush=True)
    session = None
    try:
        session = start('solver', a.cores)
        print('FLUENT_VERSION', session.get_fluent_version(), flush=True)
        session.settings.file.read_case_data(file_name=str(src))
        s = session.settings
        print('FLOW_TIME_START', s.solution.run_calculation.transient_controls.flow_time.get_state(), flush=True)
        print('REFERENCE', s.setup.reference_values.get_state(), flush=True)
        print('INLET', s.setup.boundary_conditions.velocity_inlet['inlet'].get_state(), flush=True)
        methods = s.solution.methods
        coupling = methods.p_v_coupling.flow_scheme
        print('COUPLING_ALLOWED', coupling.allowed_values(), flush=True)
        coupling.set_state('Coupled')
        print('COUPLING_READBACK', coupling.get_state(), flush=True)
        time = s.setup.general.solver.time
        print('TIME_ALLOWED', time.allowed_values(), flush=True)
        allowed = time.allowed_values()
        bounded = [v for v in allowed if 'bounded' in v.lower() and ('second' in v.lower() or '2nd' in v.lower())]
        if bounded:
            time.set_state(bounded[0])
        elif time.get_state() != 'unsteady-2nd-order':
            time.set_state('unsteady-2nd-order')
        print('TIME_READBACK', time.get_state(), 'BOUNDED_AVAILABLE', bool(bounded), flush=True)
        spatial = methods.spatial_discretization.discretization_scheme
        print('SPATIAL_BEFORE', spatial.get_state(), flush=True)
        for name in spatial.get_object_names():
            leaf = spatial[name]
            values = leaf.allowed_values()
            print('SPATIAL_OPTIONS', name, values, flush=True)
            if name.lower() in ('momentum','k','omega','turbulent kinetic energy','specific dissipation rate'):
                second = [v for v in values if 'second' in v.lower() and 'upwind' in v.lower()]
                if not second: raise RuntimeError('no second-order upwind for '+name)
                leaf.set_state(second[0])
        print('SPATIAL_READBACK', spatial.get_state(), flush=True)
        r = s.solution.monitor.residual
        print('CRITERION_ALLOWED', r.options.criterion_type.allowed_values(), flush=True)
        print('CRITERION_BEFORE', r.options.criterion_type.get_state(), flush=True)
        # Absolute 1e-5 is a permitted alternative to three-decade per-step reduction.
        choices = r.options.criterion_type.allowed_values()
        absolute = [v for v in choices if 'absolute' in v.lower()]
        if absolute: r.options.criterion_type.set_state(absolute[0])
        else: raise RuntimeError('absolute residual criterion unavailable')
        eq = r.equations
        for name in eq.get_object_names():
            state = eq[name].get_state()
            if state.get('monitor', False):
                eq[name].absolute_criteria = 1e-5
                eq[name].check_convergence = True
            print('RESIDUAL_READBACK', name, eq[name].get_state(), flush=True)
        print('CRITERION_READBACK', r.options.criterion_type.get_state(), flush=True)
        reports = s.solution.monitor.report_files
        for name in ('cd', 'cl'):
            if name not in reports.get_object_names(): raise RuntimeError('missing '+name+' report')
            reports[name].file_name = str(root / (name+'.out'))
            print('REPORT_READBACK', name, reports[name].get_state(), flush=True)
        controls = s.solution.run_calculation.transient_controls
        controls.time_step_size = a.dt
        print('DT_READBACK', controls.time_step_size.get_state(), flush=True)
        print('MAX_ITER_PER_STEP', 50, 'STEPS', a.steps, flush=True)
        s.solution.run_calculation.dual_time_iterate(time_step_count=a.steps,max_iter_per_step=50)
        print('FLOW_TIME_END', controls.flow_time.get_state(), flush=True)
        target = root / 'pilot_final.cas.h5'
        s.file.write_case_data(file_name=str(target))
        for f in sorted(root.glob('*.h5')): print('FINAL_SHA256', f, sha(f), flush=True)
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        close(session)
        print('SESSION_CLOSED', True, flush=True)

if __name__ == '__main__': main()
