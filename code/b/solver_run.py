"""CRC-only PyFluent solver stage. Logs every readback; fails on missing settings."""
import argparse
import hashlib
import json
import re
import traceback
from pathlib import Path
from launch import start, close
from mesh import generate


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def mark(name, value):
    print(name, repr(value), flush=True)


def verify_fluent_mesh_check(text):
    """G1 is fail-closed: a clean Fluent mesh check is mandatory."""
    bad = (r'non-positive volume', r'left-handed face', r'wrong node order',
           r'mesh check failed', r'negative volume')
    if any(re.search(pattern, text, re.I) for pattern in bad):
        raise RuntimeError('G1 failed: Fluent reported non-positive volumes/left-handed faces; see mesh_check.trn')
    volumes = re.findall(r'minimum volume\s*\([^)]*\)\s*:\s*([+-]?[\d.eE+-]+)', text, re.I)
    if not volumes or any(float(value) <= 0 for value in volumes):
        raise RuntimeError('G1 failed: missing or non-positive Fluent minimum volume in mesh_check.trn')
    if not re.search(r'Checking mesh.*?Done\.', text, re.I | re.S):
        raise RuntimeError('G1 failed: Fluent check completion evidence missing')
    return min(map(float, volumes))


def verify_spec(cfg):
    """L26.10 suggestion: the case file must agree with itself (Re = U*D/nu).
    G2 compares readback with the same cfg, so a wrong cfg value passes G2."""
    re_cfg = cfg['u'] * cfg['d'] / cfg['nu']
    if abs(re_cfg - cfg['re']) > 1e-6 * cfg['re']:
        raise RuntimeError(f"SPEC Re mismatch: u*d/nu={re_cfg} != re={cfg['re']}")


def verify_mesh_count(text, grid):
    """L26.10 suggestion: Fluent's own cell count must equal the requested grid."""
    m = re.search(r'^\s*0\s+(\d+)\s+\d+\s+\d+', text, re.M)
    expected = 4 * grid['side_divisions'] * grid['radial_divisions']
    if not m or int(m.group(1)) != expected:
        raise RuntimeError(f"mesh cell count {m.group(1) if m else 'missing'} != requested {expected}")


def verify_g2(solver, cfg):
    """Fail before initialization if the actual Fluent settings differ."""
    s = solver.settings.setup
    inlet = s.boundary_conditions.velocity_inlet['inlet']
    momentum = inlet.momentum
    method = momentum.velocity_specification_method.get_state()
    components = momentum.velocity_components.get_state()
    material = s.materials.fluid['air']
    refs = s.reference_values
    observed = {
        'velocity_method': method,
        'velocity_components': components,
        'air_density': material.density.value.get_state(),
        'air_viscosity': material.viscosity.value.get_state(),
        'reference_area': refs.area.get_state(),
        'reference_length': refs.length.get_state(),
        'reference_velocity': refs.velocity.get_state(),
        'reference_density': refs.density.get_state(),
        'reference_viscosity': refs.viscosity.get_state(),
        'reference_depth': refs.depth.get_state(),
    }
    mark('G2_AUDIT', observed)
    if method != 'Components' or not isinstance(components, list) or len(components) < 2:
        raise RuntimeError('G2 inlet method/components mismatch')
    def equal(actual, expected):
        return abs(float(actual) - float(expected)) <= 1e-8 * max(1.0, abs(float(expected)))
    for index, expected in enumerate((cfg['u'], 0.0)):
        comp = components[index]
        if not isinstance(comp, dict) or comp.get('option') != 'value' or not equal(comp.get('value'), expected):
            raise RuntimeError(f'G2 velocity component {index} mismatch: {comp}')
    if any(comp.get('option') != 'value' or not equal(comp.get('value'), 0)
           for comp in components[2:]):
        raise RuntimeError('G2 unexpected nonzero extra velocity component')
    for field, expected in (('air_density', cfg['rho']),
                            ('air_viscosity', cfg['rho'] * cfg['nu']),
                            ('reference_area', cfg['d']),
                            ('reference_length', cfg['d']),
                            ('reference_velocity', cfg['u']),
                            ('reference_density', cfg['rho']),
                            ('reference_viscosity', cfg['rho'] * cfg['nu']),
                            ('reference_depth', cfg['d'])):
        if not equal(observed[field], expected):
            raise RuntimeError(f'G2 {field} mismatch: {observed[field]} != {expected}')
    mark('G2_PASSED', True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--grid', default='coarse')
    p.add_argument('--model', default='sst')
    p.add_argument('--cores', type=int, default=4)
    p.add_argument('--steps', type=int, default=200)
    a = p.parse_args()
    cfg = json.loads(Path(a.case).read_text())
    grid = next(g for g in cfg['grids'] if g['name'] == a.grid)
    verify_spec(cfg)
    root = Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    mesh = root / 'source.msh'
    mark('GRID_GENERATED', generate(mesh, grid['side_divisions'], grid['radial_divisions'], grid['beta']))
    mark('GRID_SHA256', sha(mesh))
    session = None
    try:
        session = start('solver', a.cores)
        mark('FLUENT_VERSION', session.get_fluent_version())
        mark('PYFLUENT_VERSION', __import__('ansys.fluent.core', fromlist=['__version__']).__version__)
        mark('READ_MESH_START', str(mesh))
        transcript = root / 'mesh_check.trn'
        session.settings.file.start_transcript(file_name=str(transcript))
        session.settings.file.read_mesh(file_name=str(mesh))
        session.tui.mesh.check()
        session.tui.mesh.size_info()
        session.settings.file.stop_transcript()
        mark('G1_FLUENT_MIN_VOLUME', verify_fluent_mesh_check(transcript.read_text()))
        verify_mesh_count(transcript.read_text(), grid)
        mark('BOUNDARY_VELOCITY_INLET', session.settings.setup.boundary_conditions.velocity_inlet.get_object_names())
        mark('BOUNDARY_PRESSURE_OUTLET', session.settings.setup.boundary_conditions.pressure_outlet.get_object_names())
        mark('BOUNDARY_WALL', session.settings.setup.boundary_conditions.wall.get_object_names())
        from setup import configure
        mark('CONFIGURED_BOUNDARY_LIST', configure(session, cfg, a.model))
        mark('MODEL_READBACK', session.settings.setup.models.viscous.get_state())
        mark('TIME_READBACK', session.settings.setup.general.solver.time.get_state())
        if session.settings.setup.general.solver.time.get_state() != 'unsteady-2nd-order':
            raise RuntimeError('time scheme readback mismatch')
        mark('REFERENCE_READBACK', session.settings.setup.reference_values.get_state())
        mark('INLET_READBACK', session.settings.setup.boundary_conditions.velocity_inlet['inlet'].get_state())
        verify_g2(session, cfg)
        # Report definitions are coefficients (not raw forces); monitor files record every physical step.
        defs = session.settings.solution.report_definitions
        for name, kind, vector in [('cd','drag',[1,0,0]), ('cl','lift',[0,1,0])]:
            group = getattr(defs, kind)
            group[name] = {}
            group[name] = {'zones':['cylinder'], 'force_vector':vector}
            mark('REPORT_DEFINITION_'+name, group[name].get_state())
            files = session.settings.solution.monitor.report_files
            files.create(name=name)
            files[name] = {'report_defs':[name], 'file_name':str(root / (name+'.out'))}
            mark('REPORT_FILE_'+name, files[name].get_state())
        s = session.settings
        s.solution.run_calculation.transient_controls.time_step_size = cfg['dt']
        mark('DT_READBACK', s.solution.run_calculation.transient_controls.time_step_size.get_state())
        s.solution.initialization.hybrid_initialize()
        mark('INITIALIZED', True)
        mark('SOLVE_STEPS', a.steps)
        s.solution.run_calculation.dual_time_iterate(time_step_count=a.steps, max_iter_per_step=25)
        mark('SOLVE_RETURNED', a.steps)
        final = root / f"{a.model}_{a.grid}_final.cas.h5"
        s.file.write_case_data(file_name=str(final))
        for f in sorted(root.glob('*.h5')):
            mark('FINAL_SHA256', (str(f), sha(f)))
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        close(session)
        mark('SESSION_CLOSED', True)


if __name__ == '__main__':
    main()
