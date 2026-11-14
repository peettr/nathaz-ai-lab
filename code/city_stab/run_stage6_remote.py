"""Colab-only stage6_noT runner: FP32 no-model, official 12-point profile, TEMPERATURE off.

Stop criteria identical to stage3 v3: max|u|>0.3 or rho outside [0.90,1.10] after t>=3000
(host readback monitor, 50-step cadence as in stage3). On clean exit 0, run the 80-point
extraction exactly as the nan_v2 runner did.
"""
from pathlib import Path
import csv, json, os, shutil, subprocess, tarfile, time, traceback, hashlib
R = Path('/content/luw_stage6_noT_r2_1016')
R.mkdir(exist_ok=False)
def log(s):
    with (R / 'progress.log').open('a', buffering=1) as f: f.write(str(s) + '\n')
    print(s, flush=True)
def inspect(path):
    if not path.exists(): return None
    with path.open() as f: lines = f.readlines()
    if len(lines) < 2: return None
    q = dict(zip(lines[0].strip().split(','), lines[-1].strip().split(',')))
    n = int(q['step']); v = float(q['max_u_lattice']); lo = float(q['min_rho']); hi = float(q['max_rho'])
    reason = ('nonfinite ' + q['first_nonfinite_xyz_component']) if q['first_nonfinite_xyz_component'] else ('speed > .3' if v > .3 else ('rho outside [.90,1.10]' if n >= 3000 and (lo < .9 or hi > 1.1) else None))
    return {'step': n, 'max_u': v, 'lo': lo, 'hi': hi, 'mass': float(q['mass_fluid']), 'reason': reason, 'location': q['first_nonfinite_xyz_component']}
try:
    with tarfile.open('/content/city_stage6noT_inputs.tar.gz') as tar: tar.extractall(R, filter='data')
    p = R / 'FluidX3D/src/defines.hpp'; s = p.read_text()
    assert s.count('//#define CITY_STABILITY_MONITOR') == 1
    s = s.replace('//#define CITY_STABILITY_MONITOR', '#define CITY_STABILITY_MONITOR')
    assert all(('#define ' + macro) not in s.splitlines() for macro in ('GROUND_WALL_MODEL', 'FP16C', 'FP16S', 'GROUND_WALL_FILTER', 'TEMPERATURE'))
    assert any(l.startswith('#define VOLUME_FORCE') for l in s.splitlines())
    assert any(l.startswith('#define FORCE_FIELD') for l in s.splitlines())
    p.write_text(s)
    log('defines: monitor on, TEMPERATURE off, VOLUME_FORCE/FORCE_FIELD on')
    with (R / 'build.log').open('w') as f:
        res = subprocess.run(['make', 'Linux', '-j4'], cwd=R / 'FluidX3D', stdout=f, stderr=subprocess.STDOUT, timeout=900)
    log('BUILD ' + str(res.returncode)); assert res.returncode == 0, (R / 'build.log').read_text()[-4000:]
    case = R / 'case'; trace = case / 'RESULTS/city_stability.csv'
    t0 = time.time()
    with (R / 'solver.log').open('w', buffering=1) as f:
        proc = subprocess.Popen([str(R / 'FluidX3D/bin/FluidX3D'), str(case / 'conf.luwpf')], cwd=case, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT)
        seen = -1; reason = None
        while proc.poll() is None:
            time.sleep(8)
            row = inspect(trace)
            if row and row['step'] != seen:
                seen = row['step']; (R / 'latest.json').write_text(json.dumps(row))
                if seen % 1000 == 0: log('STEP ' + str(row))
                if row['reason']:
                    reason = row['reason']; log('STABILITY_STOP ' + reason + ' step=' + str(seen)); proc.terminate()
                    try: proc.wait(timeout=30)
                    except subprocess.TimeoutExpired: proc.kill()
                    break
            if time.time() - t0 > 2400:
                reason = 'budget walltime'; proc.terminate(); log('TIMEOUT budget'); break
        code = proc.wait(timeout=60)
    (R / 'solver.exit').write_text(str(code) + '\n')
    log('SOLVER_EXIT ' + str(code) + ' reason=' + str(reason) + ' elapsed=' + str(int(time.time() - t0)))
    if code == 0 and reason is None:
        (R / 'solver_a.exit').write_text('exit=0\n')
        (R / 'case_a').symlink_to(case, target_is_directory=True)
        shutil.copy2('/content/points_w_r7.json', R / 'points_w_r7.json')
        script = Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')", f"Path('{R}')")
        (R / 'extract_city.py').write_text(script)
        with (R / 'extract.log').open('w') as f:
            e = subprocess.run(['python3', str(R / 'extract_city.py')], cwd=R, stdout=f, stderr=subprocess.STDOUT, timeout=600)
        log('EXTRACT ' + str(e.returncode))
        if e.returncode: log((R / 'extract.log').read_text(errors='replace')[-2000:])
except Exception:
    (R / 'error.txt').write_text(traceback.format_exc()); log('ERROR ' + traceback.format_exc()[-3000:])
finally:
    (R / 'all.done').write_text('done\n')
