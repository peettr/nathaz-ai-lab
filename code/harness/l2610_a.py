"""L26.10 baseline A harness (cold start, mirrors T28 solver_run.main).

Observe mode: T28 checks (L0) are called verbatim from the snapshot; when one
raises we print L0_BLOCK and keep going where physically possible, so L1/L2
can be scored on the same run. T28 itself would have stopped at that point.

Injection JSON keys (all optional):
  cfg_overrides  dict   S2: change the spec (case.json) before setup
  grid           str    mesh grid name to generate (default coarse)
  mesh_mut       str    flip_all | flip_one | empty
  s1             dict   S1: values written after configure, spec untouched
                        inlet_normal: bool, inlet_components: [u, v], air_viscosity: float
  spec_inlet     bool   S2 direction: setup follows cfg['v'] / cfg['inlet_method']
  setup_module   str    path to an alternative setup.py (R-b)
  case_file      str    path to an alternative case.json (R-b)
"""
import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from l2610_common import mark, sha, start_solver, audit, mesh_size  # noqa: E402


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mutate_mesh(path, how):
    text = Path(path).read_text().splitlines(keepends=True)
    if how == 'empty':
        Path(path).write_text('(0 "L26.10 M6 empty mesh")\n(2 2)\n')
        return 'empty'
    out, in_faces, flipped = [], False, 0
    for line in text:
        if line.startswith('(13 (') and line.rstrip().endswith('('):
            in_faces = True
            out.append(line)
            continue
        if in_faces and line.startswith('))'):
            in_faces = False
        if in_faces:
            parts = line.split()
            if len(parts) == 4 and (how == 'flip_all' or (how == 'flip_one' and flipped == 0 and parts[3] != '0')):
                parts[0], parts[1] = parts[1], parts[0]
                line = ' '.join(parts) + '\n'
                flipped += 1
        out.append(line)
    Path(path).write_text(''.join(out))
    return flipped


def set_inlet(session, cfg, normal=False, comps=None):
    inlet = session.settings.setup.boundary_conditions.velocity_inlet['inlet']
    mom = inlet.momentum
    if normal:
        allowed = mom.velocity_specification_method.allowed_values()
        choice = [v for v in allowed if 'normal' in v.lower()]
        mark('INJ_NORMAL_ALLOWED', allowed)
        mom.velocity_specification_method = choice[0]
        try:
            mom.velocity_magnitude.value = cfg['u']
        except Exception:
            mom.velocity_magnitude = cfg['u']
    elif comps is not None:
        mom.velocity_specification_method = 'Components'
        mom.velocity_components = [{'option': 'value', 'value': float(c)} for c in comps]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--inj', default='{}')
    p.add_argument('--steps', type=int, default=200)
    a = p.parse_args()
    inj = json.loads(a.inj)
    snap = Path(a.snapshot).resolve()
    sys.path.insert(0, str(snap / '10_Pipeline'))
    sr = load_module('t28_solver_run', snap / '10_Pipeline' / 'solver_run.py')   # L0 verbatim
    mesh_mod = load_module('t28_mesh', snap / '10_Pipeline' / 'mesh.py')
    setup_path = Path(inj.get('setup_module', snap / '10_Pipeline' / 'setup.py'))
    setup_mod = load_module('setup_under_test', setup_path)
    case_path = Path(inj.get('case_file', snap / '20_Cases' / 'sqcyl2d' / 'case.json'))
    cfg = json.loads(case_path.read_text())
    base = json.loads((snap / '20_Cases' / 'sqcyl2d' / 'case.json').read_text())
    for k in ('grids',):
        cfg.setdefault(k, base[k])
    cfg.update(inj.get('cfg_overrides', {}))
    mark('INJ', inj)
    mark('SETUP_SHA256', sha(setup_path))
    mark('CASE_SHA256', sha(case_path))
    mark('CFG_EFFECTIVE', {k: v for k, v in cfg.items() if k != 'grids'})
    root = Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    grid = next(g for g in base['grids'] if g['name'] == inj.get('grid', 'coarse'))
    mesh = root / 'source.msh'
    mark('GRID_GENERATED', mesh_mod.generate(mesh, grid['side_divisions'], grid['radial_divisions'], grid['beta']))
    if inj.get('mesh_mut'):
        mark('MESH_MUTATION', (inj['mesh_mut'], mutate_mesh(mesh, inj['mesh_mut'])))
    mark('GRID_SHA256', sha(mesh))
    session = None
    try:
        session = start_solver(1)
        mark('FLUENT_VERSION', session.get_fluent_version())
        trn = root / 'mesh_check.trn'
        session.settings.file.start_transcript(file_name=str(trn))
        try:
            session.settings.file.read_mesh(file_name=str(mesh))
            session.tui.mesh.check()
        except Exception as exc:
            mark('READ_OR_CHECK_ERROR', repr(exc)[:300])
        finally:
            session.settings.file.stop_transcript()
        try:
            mesh_size(session, root)
        except Exception as exc:
            mark('MESH_SIZE_ERROR', repr(exc)[:300])
        try:
            mark('G1_FLUENT_MIN_VOLUME', sr.verify_fluent_mesh_check(trn.read_text()))
        except Exception as exc:
            mark('L0_BLOCK', ('G1', repr(exc)[:300]))
        try:
            mark('CONFIGURED_BOUNDARY_LIST', setup_mod.configure(session, cfg, 'sst'))
        except Exception as exc:
            mark('L0_BLOCK', ('setup', repr(exc)[:300]))
        s1 = inj.get('s1', {})
        if inj.get('spec_inlet'):
            set_inlet(session, cfg, normal=cfg.get('inlet_method') == 'normal',
                      comps=None if cfg.get('inlet_method') == 'normal' else [cfg['u'], cfg.get('v', 0.0)])
        if s1.get('inlet_normal') or 'inlet_components' in s1:
            set_inlet(session, cfg, normal=bool(s1.get('inlet_normal')), comps=s1.get('inlet_components'))
        if 'air_viscosity' in s1:
            session.settings.setup.materials.fluid['air'].viscosity.value = s1['air_viscosity']
        audit(session)
        try:
            sr.verify_g2(session, cfg)
        except Exception as exc:
            mark('L0_BLOCK', ('G2', repr(exc)[:300]))
        defs = session.settings.solution.report_definitions
        files = session.settings.solution.monitor.report_files
        for name, kind, vector in [('cd', 'drag', [1, 0, 0]), ('cl', 'lift', [0, 1, 0])]:
            group = getattr(defs, kind)
            group[name] = {}
            group[name] = {'zones': ['cylinder'], 'force_vector': vector}
            files.create(name=name)
            files[name] = {'report_defs': [name], 'file_name': str(root / (name + '.out'))}
        s = session.settings
        s.solution.run_calculation.transient_controls.time_step_size = cfg['dt']
        mark('DT_READBACK', s.solution.run_calculation.transient_controls.time_step_size.get_state())
        s.solution.initialization.hybrid_initialize()
        mark('INITIALIZED', True)
        s.solution.run_calculation.dual_time_iterate(time_step_count=a.steps, max_iter_per_step=25)
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
