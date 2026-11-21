"""Build the BG Lead-review draft only from verified terminal archives."""
from pathlib import Path
import hashlib, json, math, re, zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent.parent / '04_Handoffs/C38.2_bg_pointvalues_draft_20261115.md'
CASES = [('BG_1H', 'BG_1H_retry3_20261115_0906'), ('BG_3H', 'BG_3H_retry2_20261115_0915')]

def sha(data): return hashlib.sha256(data).hexdigest()
def fmt(x): return f'{x:.6f}' if isinstance(x,(float,int)) and math.isfinite(x) else 'NA'
def load_case(label, dirname):
    base = ROOT / dirname
    state = json.loads((base/'controller_state.json').read_text())
    assert state['event'] == 'session_stopped' and state['CU_estimate'] < 4, (label,state)
    archive = base/(label+'_result.zip')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        required = {'geometry_gate.json','solver_exit.json','calibration_1000.json','pointvalues.json','profiles_upstream.json','profiles_open_streets.json','vtk_header_sha256.json','sha256.json','solver.log','run.log'}
        assert required <= names, (label, required-names)
        manifest = json.loads(z.read('sha256.json'))
        assert all(sha(z.read(n)) == h for n,h in manifest.items())
        fields = {n:json.loads(z.read(n)) for n in required if n.endswith('.json') and n != 'sha256.json'}
        solver = z.read('solver.log').decode(errors='replace')
        runlog = z.read('run.log').decode(errors='replace')
        assert fields['solver_exit.json']['exit'] == 0
        assert 'GEOMETRY_GATE_PASS' in runlog
        assert fields['geometry_gate.json']['floating'] == 0
        steps = re.findall(r'Run steps\s*\|\s*(\d+)', solver)
        samples = re.findall(r'Avg samples\s*\|\s*(\d+)', solver)
        assert steps and samples and 'Task finished' in solver
        assert int(steps[-1]) == int(fields['pointvalues.json']['source_vtk'].split('avg-')[-1].split('.')[0])
        rows = fields['pointvalues.json']['rows']
        assert len(rows) > 0 and fields['pointvalues.json']['mixed'] == sum(bool(r['solid_corners']) for r in rows)
        assert fields['pointvalues.json']['clamped'] == sum(bool(r['clamped']) for r in rows)
        assert fields['vtk_header_sha256.json']['vtk_sha256'] == fields['pointvalues.json']['source_vtk_sha256']
        return dict(label=label, base=base, state=state, fields=fields, manifest=manifest, archive_sha=sha(archive.read_bytes()), steps=int(steps[-1]), samples=int(samples[-1]))

def main():
    assert not OUT.exists(), f'Existing draft must not be overwritten: {OUT}'
    cases=[load_case(*c) for c in CASES]
    lines=['# C38.2 building-group LUW 2 m S1 point-value draft (2026-11-15)', '',
           'Lead review only. Not released to C38.2. Speed is the magnitude of the time-mean velocity vector, not the mean of instantaneous speed.', '']
    for c in cases:
        label,f,st=c['label'],c['fields'],c['state']; p=f['pointvalues.json']; gate=f['geometry_gate.json']; h=f['vtk_header_sha256.json']; rows=p['rows']
        lines += [f'## {label}: run and geometry', '',
          f"Run root: `{c['base']}`. Colab {st['gpu']} (NVIDIA A100-SXM4-40GB, as recorded by gpu_probe); solver exit 0, {c['steps']:,} steps, {c['samples']} average samples. One terminal time-mean VTK, no time splice. Solver wall {f['solver_exit.json']['wall_seconds']:.3f} s. The exact physical averaging duration has not been independently checked.", '',
          f"Native fluid-mask gate PASS: domain {gate['dims']} cells, 2 m spacing, origin {gate['origin']} m; ground wall label {gate['ground_wall_label_m']} m, open-column first fluid index {gate['open_columns'][0]['first_fluid_k']}, low-roof samples {gate['low_roof_sample_count']}, tower-roof samples {gate['tower_roof_sample_count']}, floating structures {gate['floating']}. See archive geometry_gate.json and gate_solver.log.", '',
          f"Session creation-to-confirmed-stop duration {st['elapsed_session_s']:.3f} s; estimated {st['CU_estimate']:.6f} CU using conservative assumed {st['rate_CU_per_hour_conservative']} CU/h. This is not an invoiced debit; other attempts are excluded from this one session's figure.", '',
          f"Source and reference: C38 full-scale x is downwind (+x), y lateral, z up; signed time-mean u,v,w are +x,+y,+z m/s. VTK origin {p['origin_xyz_m']} m and spacing {p['spacing_xyz_m']} m. U_H={p['UH_mps']} m/s at H={p['UH_height_m']} m (nominal inlet reference); speed/U_H=|<u,v,w>|/U_H. Coordinates are both the source C38 labels and actual LUW sample coordinates shown below. S1 height is above effective ground wall at {p['wall_label_m']} m; clamped rows and positive-weight solid interpolation corners are explicitly flagged. This archive has {len(rows)} rows, {p['clamped']} clamped, {p['mixed']} mixed with solids; mixed rows are not counted as unobstructed fluid-site predictions.", '',
          '### Near-ground limitation', '',
          'This configuration uses a 2 m grid and flat-ground no-slip bounce-back with no wall model. The measured near-ground inlet and designated open-ground profiles below reveal configuration-dependent attenuation; the four open-ground columns include both upstream and downstream locations, so this is not solely a pre-building attenuation metric. Near-ground point errors cannot establish accuracy under an adequate wall treatment. This observation does not uniquely attribute attenuation to the wall operator rather than inflow, turbulence or other boundaries.', '',
          f"Measured inlet x=2 m, y={next(r['y_m'] for r in f['profiles_upstream.json'] if r['x_m']==2 and r['height_agl_m']==2 and r['y_m'] == gate['dims'][1])} m, 2 m AGL speed: {fmt(next(r['speed_mps'] for r in f['profiles_upstream.json'] if r['x_m']==2 and r['height_agl_m']==2 and r['y_m'] == gate['dims'][1]))} m/s. Four designated open-ground-column mean at 2 m divided by that measured inlet: {fmt(h['comparison']['open_mean_to_inlet_ratio'])}; AF comparison is not applicable to the BG inlet. The full inlet/upstream and open/street vertical profiles (including u,v,w,k and solid weight) are archived separately, hashes below.", '',
          '| Open-ground LUW x,y (m) | 2 m | 3 m | 5 m | 10 m |', '|---|---:|---:|---:|---:|']
        op=f['profiles_open_streets.json']; sites=sorted({(r['x_m'],r['y_m']) for r in op if r['group']=='open'})
        for xy in sites:
            vals={r['height_agl_m']:r for r in op if r['group']=='open' and (r['x_m'],r['y_m'])==xy}
            lines.append('| '+f'{xy[0]}, {xy[1]} | '+' | '.join(fmt(vals[z]['speed_mps']) if z in vals and vals[z]['solid_weight']==0 else 'NA (solid)' for z in (2,3,5,10))+' |')
        lines += ['', '### Evidence SHA256', '',f"- Archive `{c['base']/(label+'_result.zip')}`: `{c['archive_sha']}`", f"- Remote mean VTK (header and hash only): `{h['vtk_sha256']}`"]
        lines += [f'- Archive member `{n}`: `{digest}`' for n,digest in sorted(c['manifest'].items())]
        lines += ['', '### Per-point time-mean velocities (S1)', '',
          '| Kind | ID | Zone | C38 x,y,z (m) | LUW sample x,y,z (m) | Actual AGL (m) | u (m/s) | v (m/s) | w (m/s) | speed/U_H | Clamped | Solid corners |',
          '|---|---:|---|---|---|---:|---:|---:|---:|---:|---|---:|']
        for r in rows:
            xyz=lambda key: ', '.join(fmt(x) for x in r[key]); lines.append('| '+' | '.join([str(r['kind']),str(r['id']),str(r['zone']),xyz('c38_xyz_m'),xyz('luw_sample_xyz_m'),fmt(r['actual_agl_m']),fmt(r['u_mps']),fmt(r['v_mps']),fmt(r['w_mps']),fmt(r['speed_over_UH']),'yes' if r['clamped'] else 'no',str(len(r['solid_corners']))])+' |')
        lines.append('')
    lines += ['## BG_3H runtime prediction and budget rule', '',
      'The original 2-CU attempt used a 510 × 330 × 180 cell domain (1020 × 660 × 360 m at 2 m spacing), 43,461 requested steps, a 29,880-step mean window and stride 54. Its first-1000-step calibration took 19.297168418 s. The frozen controller used predicted full-solver-plus-export seconds = measured calibration seconds × (43,461/1,000) × 1.2 + 160 s. The 1.2 factor is a conservative overhead and 160 s reserves extraction/download/stop. The calculation is 19.297168418 × 43.461 × 1.2 + 160 = 1166.4 s (rounded); this exceeded the then-remaining 802.6 s, so that first attempt did not start the full solver. Under the subsequently authorized 4-CU cap, retry2 independently measured 19.54877123 s/1000 steps and predicted 1179.5 s by the same rule against 1931.5 s remaining. These are budget forecasts, not measured full-solver duration.', '',
      'Averaging/window counts are solver-log observations for the completed retry2, not inferred solely from the configuration. CU values cover each completed session from creation to confirmed stop and are estimates, not billing records.', '']
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text('\n'.join(lines))
    print(OUT, sha(OUT.read_bytes()), 'cases', [(c['label'],c['steps'],c['samples'],len(c['fields']['pointvalues.json']['rows'])) for c in cases])
if __name__=='__main__': main()
