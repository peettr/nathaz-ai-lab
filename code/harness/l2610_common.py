"""L26.10 harness helpers: launch with longer timeout, uniform audit mark.

Only instrumentation lives here. T28 checks (L0) are imported verbatim from the
snapshot (solver_run.verify_fluent_mesh_check / verify_g2; converged_segment raises).
"""
import hashlib
import json
import math
import sys
import time


def mark(name, value):
    print(name, repr(value), flush=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def start_solver(cores=1):
    import ansys.fluent.core as pyfluent
    # Fluent advice #f34754a7: start timeout >=300 s (CRC 1580310 timed out at 180 s).
    return pyfluent.launch_fluent(mode='solver', dimension=pyfluent.Dimension.TWO,
                                  precision=pyfluent.Precision.DOUBLE,
                                  processor_count=cores, cleanup_on_exit=True,
                                  start_timeout=300)


def _get(fn):
    try:
        return fn()
    except Exception as exc:  # recorded, never raised: audit is passive
        return {'_audit_error': repr(exc)[:200]}


def audit(session, tag='L2610_AUDIT'):
    """Read back every setting L1 needs; never changes the session."""
    s = session.settings
    inlet = s.setup.boundary_conditions.velocity_inlet['inlet']
    air = s.setup.materials.fluid['air']
    refs = s.setup.reference_values
    residual = s.solution.monitor.residual
    data = {
        'viscous': _get(lambda: s.setup.models.viscous.get_state()),
        'time': _get(lambda: s.setup.general.solver.time.get_state()),
        'air_density': _get(lambda: air.density.value.get_state()),
        'air_viscosity': _get(lambda: air.viscosity.value.get_state()),
        'inlet_method': _get(lambda: inlet.momentum.velocity_specification_method.get_state()),
        'inlet_components': _get(lambda: inlet.momentum.velocity_components.get_state()),
        'inlet_momentum': _get(lambda: inlet.momentum.get_state()),
        'reference': _get(lambda: refs.get_state()),
        'dt': _get(lambda: s.solution.run_calculation.transient_controls.time_step_size.get_state()),
        'criterion_type': _get(lambda: residual.options.criterion_type.get_state()),
        'residual_equations': _get(lambda: {n: residual.equations[n].get_state()
                                            for n in residual.equations.get_object_names()}),
    }
    mark(tag, data)
    return data


def mesh_size(session, root):
    """Write mesh size info to a transcript for L1 K09 (instrumentation only)."""
    trn = root / 'mesh_size.trn'
    session.settings.file.start_transcript(file_name=str(trn))
    try:
        session.tui.mesh.size_info()
    finally:
        session.settings.file.stop_transcript()
    mark('MESH_SIZE_TRN', str(trn))
