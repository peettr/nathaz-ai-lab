from pathlib import Path
from zipfile import ZipFile
import json, hashlib, math
root = Path(__file__).resolve().parent
base = root.parents[2]
archive = root/'caseD_result.zip'
out = base/'04_Handoffs'/'C38.2_caseD_bg_pointvalues_draft_20261115.md'
assert not out.exists(), 'Do not overwrite existing draft'
with ZipFile(archive) as z:
    assert z.testzip() is None
    hashes = json.loads(z.read('sha256.json'))
    assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in hashes.items())
    data=json.loads(z.read('pointvalues.json'))
    rows=data['rows']
assert len(rows)==99 and len({(r['kind'],r['id']) for r in rows})==99
assert data['clamped']==sum(bool(r['clamped']) for r in rows)
assert data['mixed']==sum(bool(r['solid_corners']) for r in rows)
assert all(math.isfinite(r[k]) for r in rows for k in ('u_mps','v_mps','w_mps','speed_over_UH'))
assert all(abs(math.sqrt(sum(r[k]**2 for k in ('u_mps','v_mps','w_mps')))/data['UH_mps']-r['speed_over_UH'])<1e-9 for r in rows)
state=json.loads((root/'controller_state.json').read_text())
manifest=json.loads((base/'06_Logs/C38.2_caseD_bg/CaseD/stage/manifest.json').read_text())
lines=['# AIJ Case D: LUW round-9 2 m S1 per-point draft (2026-11-15)',
'','Status: Case D only; BG_1H and BG_3H are not included in this table. This is a time-mean vector-magnitude prediction, not the hot-wire mean scalar speed.',
'','## Run and sampling definition',
'',f"Colab ordinary A100; source case D solver finished 33,767 steps (exit 0), 553 averaged samples. Prescribed terminal window: last 23,215 steps, stride 42 (rounded from the Case A H/U_H scaling). The solver log reports 31 min 20 s solver time, 31 min 28 s including preprocessing. Mean VTK: `{data['source_vtk']}`. A single time-mean field was sampled; no temporal splice. Physical averaging duration was not independently verified.",
'',f"C38 full-scale coordinates: x along the incoming wind (+x), y lateral, z up, in metres; x_LUW=x_C38+850 m, y_LUW=y_C38+550 m. The native VTK origin is {data['origin_xyz_m']} m, spacing {data['spacing_xyz_m']} m. Signed time-mean u,v,w are +x,+y,+z components in m/s. U_H={data['UH_mps']} m/s is the Case D nominal inlet/reference velocity at H={data['UH_height_m']} m; speed/U_H=|<u,v,w>|/U_H. Do not equate this with <|u|>/U_H of a scalar-speed instrument.",
'',f"S1: physical measurement z is height above the effective open-ground wall. The wall label is {data['wall_label_m']} m, midway between the highest solid and first fluid centre. The LUW sample label equals wall label plus C38 height; points lower than the first fluid centre are clamped and marked. A positive-weight solid interpolation corner is listed separately as mixed. Case D: {data['clamped']} clamped and {data['mixed']} mixed among {len(rows)} rows. The ground mask and tower/low-roof checks are in `geometry_gate.json` inside the result archive.",
'',f"Session creation-to-confirmed-stop {state['elapsed_session_s']:.3f} s; estimated CU={state['CU_estimate']:.6f} using conservative {state['rate_CU_per_hour_conservative']} CU/h. This is not a verified billing debit; it is within the authorized 7 CU Case D cap.",
'','## SHA256 provenance','',
f"- `06_Logs/C38.2_caseD_bg/CaseD_retry6_20261115_0411/caseD_result.zip`: {hashlib.sha256(archive.read_bytes()).hexdigest()}",
f"- Remote mean VTK (source hash recorded by extractor; no full VTK retained locally): {data['source_vtk_sha256']}"]
for name,h in sorted(hashes.items()): lines.append(f'- Archive member `{name}`: {h}')
for name in ('controller.log','controller_state.json','stl_consistency.json'):
    p=root/name
    if p.is_file(): lines.append(f'- `06_Logs/C38.2_caseD_bg/{root.name}/{name}`: {hashlib.sha256(p.read_bytes()).hexdigest()}')
for name in ('source_dd438c1.tar.gz','caseD/conf.luwpf','caseD/CaseD_PF.stl','caseD/wind_bc/profile.dat'):
    p=base/'06_Logs/caseA_r9_2m_tacc_v2/stage'/name
    if p.exists(): lines.append(f'- Baseline `{name}`: {hashlib.sha256(p.read_bytes()).hexdigest()}')
lines += ['','## Per-point time-mean velocities','','C38 coordinates and LUW sample coordinates are both in metres. S/T retain their source labels; repeated locations can occur in separate groups. Numerical columns are rounded for display; full precision is in `pointvalues.json` in the archive.','','| Group | ID | C38 x,y,z (m) | LUW sample x,y,z (m) | Actual AGL (m) | u (m/s) | v (m/s) | w (m/s) | speed/U_H | Clamped | Mixed |','|---|---:|---|---|---:|---:|---:|---:|---:|---|---|']
for r in rows:
    xyz=lambda key: ', '.join(f'{v:.3f}' for v in r[key])
    lines.append(f"| {r['kind']} | {r['id']} | {xyz('c38_xyz_m')} | {xyz('luw_sample_xyz_m')} | {r['actual_agl_m']:.3f} | {r['u_mps']:.9f} | {r['v_mps']:.9f} | {r['w_mps']:.9f} | {r['speed_over_UH']:.9f} | {'yes' if r['clamped'] else 'no'} | {len(r['solid_corners'])} |")
lines += ['','SHA256 of this Markdown draft is reported separately in the handoff message (a file cannot contain its own cryptographic hash without changing it).','']
out.write_text('\n'.join(lines))
print(out)
print('rows',len(rows),'SHA256',hashlib.sha256(out.read_bytes()).hexdigest())
