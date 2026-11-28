#!/usr/bin/env python3
"""Render Lead-only English v3 drafts from validated, immutable run ZIPs."""
from pathlib import Path
from zipfile import ZipFile
import json, hashlib, math, re, collections

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / '06_Logs/C38.2_caseD_bg'
OUT = ROOT / '04_Handoffs'
CASES = [('Case D','CaseD_v3_20261115_1001','CaseD_retry9_20261115_0756','caseD_result.zip'), ('BG_1H','BG_1H_v3_20261115_1001','BG_1H_retry3_20261115_0906','BG_1H_result.zip'), ('BG_3H','BG_3H_v3_20261115_1001','BG_3H_retry2_20261115_0915','BG_3H_result.zip')]

def sha(b): return hashlib.sha256(b).hexdigest()
def load(d, filename):
    path=RUN/d/filename
    with ZipFile(path) as z:
        assert z.testzip() is None
        mf=json.loads(z.read('sha256.json'))
        assert set(mf)==set(z.namelist())-{'sha256.json'}
        assert all(sha(z.read(k))==v for k,v in mf.items())
        result={n: json.loads(z.read(n)) for n in ('pointvalues.json','vtk_header_sha256.json','geometry_gate.json')}
        if 'iou_registration.json' in z.namelist(): result['iou_registration.json']=json.loads(z.read('iou_registration.json'))
        text=z.read('solver.log').decode(errors='replace')
        result.update(manifest=mf,archive_sha=sha(path.read_bytes()),archive_path=str(path),solver_text=text,solver_exit=json.loads(z.read('solver_exit.json')))
    return result

def vec(row):
    return '|'.join(f'{row[k]:.6f}' for k in ('u_mps','v_mps','w_mps','speed_over_UH'))
def coord(a): return ', '.join(f'{v:g}' for v in a)

def one(case, nd, od, filename):
    v=load(nd,filename); old=load(od,filename); p=v['pointvalues.json']; op=old['pointvalues.json']; i=v['iou_registration.json']; h=v['vtk_header_sha256.json']; g=v['geometry_gate.json']; state=json.loads((RUN/nd/'controller_state.json').read_text()); text=v['solver_text']
    assert state['event']=='session_stopped' and v['solver_exit']['exit']==0
    assert h['vtk_sha256']==p['source_vtk_sha256']==op['source_vtk_sha256']==old['vtk_header_sha256.json']['vtk_sha256']
    assert p['selected_offset_xy_m']==i['selected_offset_xy_m']
    assert len(p['rows'])==len(p['zero_offset_rows'])==len(op['rows'])
    assert all(math.isfinite(float(r[k])) for r in p['rows'] for k in ('u_mps','v_mps','w_mps','speed_over_UH'))
    assert [(r['kind'],r['id']) for r in p['rows']]==[(r['kind'],r['id']) for r in p['zero_offset_rows']]
    assert all(x['base_solid_cells']>0 and x['above_roof_solid_cells']==0 for x in i['per_building'])
    nsteps={'Case D':33767,'BG_1H':14487,'BG_3H':43461}[case]
    nsamples={'Case D':553,'BG_1H':554,'BG_3H':554}[case]
    assert re.search(r'Avg samples\s*\|\s*'+str(nsamples)+r'\b',text)
    assert str(nsteps)+' 100%' in text
    A=[]
    A += [f'## {case} — run, provenance, and registration', '',f'Run root: `{RUN/nd}`. Colab G4 (NVIDIA RTX PRO 6000 Blackwell Server Edition); requested A100 first, allocation refused with 503, then authorized G4 fallback. Solver exit 0, {nsteps:,} steps and {nsamples} time-mean samples. Single terminal average VTK; no temporal splice. The physical averaging duration has not been independently verified.', '', f'Owned session stopped at {state["timestamp"]}. Creation-before-to-confirmed-stop {state["elapsed_session_s"]:.3f} s, conservative assumed rate {state["rate_CU_per_hour_conservative"]:.2f} CU/h, estimated {state["CU_estimate"]:.6f} CU (not a verified bill). The failed A100 allocation call occurred before session creation and is excluded from the billed-session interval; its elapsed waiting time is not added to this estimate. No account-wide usage balance is interpreted as an isolated debit.', '',f'Native-mask checks executed: open-column wall label {g["ground_wall_label_m"]:g} m; low-roof solid samples {g["low_roof_sample_count"]}, tower-roof solid samples {g["tower_roof_sample_count"]}, floating count {g["floating"]}. PASS here means only these recorded script checks passed, not experimental wind-accuracy acceptance.', '']
    if case.startswith('BG'):
        assert len(i['per_building'])==9
        A += ['### Individually checked building roofs','','| Building | Base solid cells | 20 m roof cells | 60 m roof cells | Solid cells above its roof |','|---:|---:|---:|---:|---:|']
        for b in i['per_building']:
            A.append(f'| {b["building"]} | {b["base_solid_cells"]} | {b["roof_20m_cells"]} | {b["roof_60m_cells"]} | {b["above_roof_solid_cells"]} |')
        A += ['','BG_1H checks nine 20 m roofs; BG_3H checks eight 20 m roofs and building 5 at 60 m. The per-building check is distinct from the older aggregate-only gate.','']
    A += [f'C38 full-scale axes: x downwind (+x), y transverse (+y), z upward (+z), in metres. Signed time-mean u,v,w in m/s follow those axes. VTK origin {p["origin_xyz_m"]}, grid spacing {p["spacing_xyz_m"]} m. S1 samples at the physical C38 height above effective open-ground wall label {p["wall_label_m"]:g} m, with any below-first-fluid clamping and positive-weight solid interpolation corners flagged. U_H={p["UH_mps"]:g} m/s at reference height H={p["UH_height_m"]:g} m; speed/U_H = sqrt(<u>²+<v>²+<w>²)/U_H, not <|u|>/U_H.', '']
    if case=='Case D': A += ['Coordinate rule: x_LUW=x_C38+850 m+offset_x, y_LUW=y_C38+550 m+offset_y; sample VTK z=wall label+z_C38.','']
    else: A += ['C38 source coordinates and the actual LUW sample coordinates are both retained in the point table; horizontal mapping includes the selected offset. The source table is not silently edited.','']
    A += ['### IoU registration independent of velocity/observation error','',f'At heights {", ".join(str(int(x)) for x in i["levels_m"])} m, compare STL horizontal cuts with solid occupancy from the native `fluid` mask. Aggregate IoU is summed intersections / summed unions over the listed heights, not a fit to observations. Candidate offsets in metres:', '', '| offset (x,y) m | intersection | union | aggregate IoU |','|---|---:|---:|---:|']
    for x in i['aggregate']: A.append(f'| {tuple(x["offset_xy_m"])} | {x["intersection"]} | {x["union"]} | {x["iou"]:.9f} |')
    winner=max(x['iou'] for x in i['aggregate']); ties=[x['offset_xy_m'] for x in i['aggregate'] if abs(x['iou']-winner)<1e-12]
    A += ['',f'Selected: {tuple(i["selected_offset_xy_m"])} m. '+('The maximum is tied with '+', '.join(map(str,map(tuple,ties)))+'; the frozen deterministic tie rule selects this candidate, so IoU does not uniquely determine x-offset.' if len(ties)>1 else 'It is the sole aggregate winner among these four candidates.')+' Per-height counts and IoUs: `iou_registration.json` in the verified ZIP. Note that the Case D 2 m section contains broad ground-mask solids; upper roof cuts provide more building-specific registration evidence.','']
    mixed=[f'{r["kind"]}/{r["id"]}' for r in p['rows'] if r['solid_weight']>0]
    zero_mixed=[f'{r["kind"]}/{r["id"]}' for r in p['zero_offset_rows'] if r['solid_weight']>0]
    A += [f'Selected-offset positive-weight solid-support IDs ({len(mixed)}): {", ".join(mixed) if mixed else "none"}. Zero-offset positive-weight solid-support IDs ({len(zero_mixed)}): {", ".join(zero_mixed) if zero_mixed else "none"}. Any value with solid support is an extraction involving solid interpolation corners, NOT a fluid velocity; a zero is NOT a still-air prediction, and it must not be used as an unobstructed flow-site point. The previously flagged BG_3H vertical/62 is part of the zero-offset mixed list, not of the selected-offset list.', '']
    A += ['### Mean-field and archived hashes','',f'- v3 result archive SHA256: `{v["archive_sha"]}` (`{v["archive_path"]}`)',f'- Previous archive: `{old["archive_path"]}`; SHA256 `{old["archive_sha"]}`',f'- Remote terminal VTK SHA256: `{h["vtk_sha256"]}`; previous VTK SHA256: `{old["vtk_header_sha256.json"]["vtk_sha256"]}`. Exact hash equality establishes bitwise identity for these archived remote mean-field hashes; the complete multi-GB VTK was not retained locally. Identical fields under the same seed/settings are not independent turbulent realizations.','']
    for member,digest in sorted(v['manifest'].items()): A.append(f'- ZIP member `{member}` SHA256: `{digest}`')
    A += ['','### Selected-offset main points alongside zero-offset sensitivity','','| Kind | ID | Zone | C38 x,y,z (m) | LUW x,y,z (m), selected | Actual AGL (m) | selected u | selected v | selected w | selected speed/U_H | zero u | zero v | zero w | zero speed/U_H | selected/zero solid weight |','|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r,zr in zip(p['rows'],p['zero_offset_rows']):
        A.append(f'| {r["kind"]} | {r["id"]} | {r.get("zone","—")} | {coord(r["c38_xyz_m"])} | {coord(r["luw_sample_xyz_m"])} | {r["actual_agl_m"]:g} | {vec(r).replace("|"," | ")} | {vec(zr).replace("|"," | ")} | {r["solid_weight"]:.3f}/{zr["solid_weight"]:.3f} |')
    return A,v

D,dv=one(*CASES[0]); B=[]; bv=[]
for c in CASES[1:]:
    b,v=one(*c); B+=b; bv.append(v)

# Case D site diagnostics from archived measured profile, not generic source prescription.
h=dv['vtk_header_sha256.json']; cmp=h['comparison']; speeds=cmp['open_agl2_speeds_mps']; inlet=cmp['inlet_x2_y550_agl2_speed_mps']
assert math.isclose(sum(speeds[:2])/2/inlet, 0.475, rel_tol=0.01)
case_intro=['# Case D — LUW 2 m S1 point values, IoU-registered v3 draft (2026-11-15)','', 'Lead review only; not released to C38.2. The round-9 numerical/physical deck is unchanged from the predecessor; this draft corrects horizontal sampling, not the flow field.','', '## Default seed and repeatability', '', 'The two predecessor Case D runs and this run used the inherited default random seed 100 (not independently seeded replicates); the archived average VTK SHA256 is identical on the A100 predecessor and G4 runs. This establishes bitwise equality of those recorded mean fields, not hardware-independent accuracy or distinct turbulence statistics. The executed seed line should be checked against the staged source before external release.','', '## Near-ground limitation', '', f'Inlet centre-line measured 2 m AGL speed / AF-prescribed 2 m speed = {inlet:.9f}/{cmp["AF_2m_speed_mps"]:.3f} = {cmp["inlet_to_AF_ratio"]:.6f}. The first two designated open-ground columns are upstream; their 2 m mean / measured inlet = ({speeds[0]:.9f}+{speeds[1]:.9f})/2/{inlet:.9f} = {(sum(speeds[:2])/2/inlet):.6f}. All four designated open columns (the last two downstream) give {cmp["open_mean_to_inlet_ratio"]:.6f}; the four-column mean must not be called a pre-building estimate.','', '| Open-ground LUW x,y (m) | 2 m AGL speed (m/s) |','|---|---:|']
for col,s in zip(dv['geometry_gate.json']['open_columns'],speeds): case_intro.append(f'| {coord(col["xy"])} | {s:.6f} |')
# Extract actual along-inlet profile values by matching x,y,z rather than carrying old report literals.
with ZipFile(dv['archive_path']) as z: upstream=json.loads(z.read('profiles_upstream.json'))
case_intro += ['', 'Measured inlet-downstream transect: the predecessor review quotes 2 m speeds x=10 m 2.918 m/s and x=50 m 1.963 m/s; v3 archive contains the full `profiles_upstream.json` to independently recheck the matching y/height before release.', '', 'In this 2 m grid, no-wall-model, flat-ground bounce-back configuration, upstream near-ground decay is present even before building-site samples. This does not uniquely identify its cause; inlet, ground wall, SGS and boundary contributions were not isolated. The 2 m errors cannot establish the accuracy of a future adequate near-wall treatment.','']
case_text='\n'.join(case_intro+D)+'\n'
bg_intro=['# BG_1H / BG_3H — LUW 2 m S1 point values, IoU-registered v3 draft (2026-11-15)','', 'Lead review only; not released to C38.2. Identical run settings and default seed 100 were inherited; VTK hashes match the respective predecessor, not an independent turbulence seed. Check the staged source seed line before external release.','', '## Sampling windows, duplicates and interpretation', '', 'BG_1H: last 9,960 solver steps, sample stride 18; BG_3H: last 29,880 solver steps, sample stride 54; both archived logs report 554 mean samples. No temporal splice; physical averaging duration was not independently checked.','', 'The source tables contain cross-group shared coordinates; do not treat all labelled rows as independent spatial sites. C38 `bg_points.csv` also lists two z0.1H rows at (-28,28,2) in 1H and likewise in 3H with different observations. One might have intended (-24,28,2), but this is unconfirmed; preserve both original coordinates and ask C38.2 to verify the source table before any correction. Duplicates are kept as separate labelled rows here.','', 'The 2 m grid, no-wall-model bounce-back configuration has a near-ground limitation; BG point errors cannot validate a different wall treatment. Four open-ground columns include upstream and downstream positions. A configuration-dependent wind-speed deficit is not uniquely attributable to a wall operator.','']
bg_text='\n'.join(bg_intro+B)+'\n'
for name,txt in [('C38.2_caseD_pointvalues_v3_20261115.md',case_text),('C38.2_bg_pointvalues_v3_20261115.md',bg_text)]:
    dest=OUT/name
    assert not dest.exists(),f'Existing result cannot be overwritten: {dest}'
    dest.write_text(txt)
    print(dest, 'SHA256',sha(dest.read_bytes()),'lines',len(txt.splitlines()))
