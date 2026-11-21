"""One restart-only Fluent URANS segment; never modifies its source pair."""
import argparse
import hashlib
import traceback
from pathlib import Path
from launch import start, close


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('source', 'root'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--dt', type=float, required=True)
    parser.add_argument('--steps', type=int, required=True)
    parser.add_argument('--cores', type=int, default=8)
    parser.add_argument('--model', choices=('sst', 'k-epsilon-kl'), required=True)
    a = parser.parse_args()
    if a.dt <= 0 or a.steps < 1 or a.cores < 1:
        raise ValueError('positive dt, steps and cores required')
    src = a.source.resolve()
    dat = src.with_name(src.name.replace('.cas.h5', '.dat.h5'))
    if not src.name.endswith('.cas.h5') or not src.is_file() or not dat.is_file():
        raise ValueError('complete immutable cas/dat source pair required')
    root = a.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for p in (src, dat):
        print('SOURCE_SHA256', p, digest(p), flush=True)
    session = None
    try:
        session = start('solver', a.cores)
        print('FLUENT_VERSION', session.get_fluent_version(), flush=True)
        session.settings.file.read_case_data(file_name=str(src))
        s = session.settings
        print('FLOW_TIME_START', s.solution.run_calculation.transient_controls.flow_time.get_state(), flush=True)
        print('REFERENCE', s.setup.reference_values.get_state(), flush=True)
        print('INLET', s.setup.boundary_conditions.velocity_inlet['inlet'].get_state(), flush=True)
        visc = s.setup.models.viscous.get_state()
        print('SOURCE_MODEL', visc, flush=True)
        if a.model == 'sst':
            if visc.get('model') != 'k-omega' or visc.get('k_omega_model') != 'sst':
                raise RuntimeError('source is not SST')
            required = {'mom', 'k', 'omega'}
        else:
            if (visc.get('model') != 'k-epsilon' or
                    not visc.get('options', {}).get('production_kato_launder_enabled')):
                raise RuntimeError('source is not Kato-Launder k-epsilon')
            required = {'mom', 'k', 'epsilon'}
        scheme = s.solution.methods.p_v_coupling.flow_scheme
        if 'Coupled' not in scheme.allowed_values():
            raise RuntimeError('Coupled not offered')
        scheme.set_state('Coupled')
        print('COUPLING_READBACK', scheme.get_state(), flush=True)
        time = s.setup.general.solver.time
        bounded = [v for v in time.allowed_values() if 'bounded' in v.lower() and ('2nd' in v.lower() or 'second' in v.lower())]
        if not bounded:
            raise RuntimeError('bounded second-order implicit unavailable')
        time.set_state(bounded[0])
        print('TIME_READBACK', time.get_state(), flush=True)
        spatial = s.solution.methods.spatial_discretization.discretization_scheme
        names = spatial.get_object_names()
        if not required.issubset(set(names)):
            raise RuntimeError('unexpected spatial schemes: '+repr(names))
        for n in required:
            leaf = spatial[n]
            if 'second-order-upwind' not in leaf.allowed_values():
                raise RuntimeError('second order unavailable for '+n)
            leaf.set_state('second-order-upwind')
        print('SPATIAL_READBACK', spatial.get_state(), flush=True)
        residual = s.solution.monitor.residual
        if 'absolute' not in residual.options.criterion_type.allowed_values():
            raise RuntimeError('absolute criterion unavailable')
        residual.options.criterion_type.set_state('absolute')
        for name in residual.equations.get_object_names():
            eq = residual.equations[name]
            if eq.get_state().get('monitor', False):
                eq.absolute_criteria = 1e-5
                eq.check_convergence = True
            print('RESIDUAL_READBACK', name, eq.get_state(), flush=True)
        print('CRITERION_READBACK', residual.options.criterion_type.get_state(), flush=True)
        reports = s.solution.monitor.report_files
        for name in ('cd', 'cl'):
            if name not in reports.get_object_names():
                raise RuntimeError('missing '+name+' report definition')
            reports[name].file_name = str(root / (name+'.out'))
            print('REPORT_READBACK', name, reports[name].get_state(), flush=True)
        controls = s.solution.run_calculation.transient_controls
        controls.time_step_size = a.dt
        if controls.time_step_size.get_state() != a.dt:
            raise RuntimeError('dt readback mismatch')
        print('DT_READBACK', controls.time_step_size.get_state(), flush=True)
        print('MAX_ITER_PER_STEP', 50, 'STEPS', a.steps, flush=True)
        s.solution.run_calculation.dual_time_iterate(time_step_count=a.steps, max_iter_per_step=50)
        print('FLOW_TIME_END', controls.flow_time.get_state(), flush=True)
        s.file.write_case_data(file_name=str(root / 'segment_final.cas.h5'))
        for p in sorted(root.glob('*.h5')):
            print('FINAL_SHA256', p, digest(p), flush=True)
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        close(session)
        print('SESSION_CLOSED', True, flush=True)

if __name__ == '__main__':
    main()
