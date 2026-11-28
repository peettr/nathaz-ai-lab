from pathlib import Path
import hashlib, json, re, zipfile
ROOT=Path('./24_Urban_Wind_LBM')
BASE=ROOT/'06_Logs/C38.2_caseD_bg'
OUT=ROOT/'04_Handoffs/C38.2_bg_pointvalues_v4_20261115.md'
def digest(b): return hashlib.sha256(b).hexdigest()
def fmt(v): return f'{v:.6f}'
def xyz(v): return ', '.join(f'{x:g}' for x in v)
parts=['# BG_1H / BG_3H — LUW 2 m S1 point values, centroid-tie-registered v4 draft (2026-11-15)', '', 'Lead review only; not released to C38.2. Case D v3 is unchanged. The two BG simulations repeat the same numerical configuration and default seed; matching VTK hashes do not constitute independent turbulence realizations. Verify the staged seed source line before external release.', '', '## Sampling windows, duplicates and interpretation', '', 'BG_1H: last 9,960 solver steps, stride 18; BG_3H: last 29,880 steps, stride 54. Both archived logs report 554 mean samples. No temporal splice; physical averaging duration not independently checked. The C38 source contains cross-group shared coordinates; labelled rows are not independent spatial sites. The 1H and 3H z0.1H source lists each repeat (-28,28,2) with different observations; (-24,28,2) is a suspected but unconfirmed correction. Preserve both source rows until C38.2 checks them.', '', 'The 2 m grid with no wall model and ground bounce-back has a near-ground limitation: these 2 m values do not establish the accuracy of a different near-wall treatment. Four open-ground columns mix upstream and downstream sites; any deficit cannot be uniquely attributed to a wall operator.', '', '## Frozen tie rule and centroid evidence', '', 'Before comparing velocities with observations, compare closed STL horizontal cuts and the native solid/fluid mask at 2 m and roof-relevant levels. For aggregate IoU ties, select each axis independently as 0 or +dx in the direction of the native-solid centroid offset relative to STL; dx=2 m. The Lead’s independent 2 m fluid-mask cross-check found three native centroids x=131.44, 171.44, 211.44 m and y=71.44 m versus the corresponding STL centres x=130, 170, 210 m and y=70 m: positive 1.44 m on both axes. Hence the frozen choice is (+2,+2) m for both BG cases, not an observation-error fit. See `04_Decisions/R21.4_C38.2_CaseD_BG_裁决_8bdc0b13_20261115.md` (11-15 11:00 supplement).', '', 'Caution: the v4 registration JSON’s `centroid_tiebreak_evidence` uses bounding-extents midpoints y=69 m for its STL reference (and native y=71.444 m), whereas the Lead’s independent STL centre is y=70 m. This 1 m reference-definition difference changes the reported y delta (2.444 vs 1.444 m), not its positive direction or the (+2,+2) choice; it must not be silently called an identical centroid measurement.', '']
for case,step,window,stride,old in [('BG_1H',14487,9960,18,'BG_1H_v3_20261115_1001'),('BG_3H',43461,29880,54,'BG_3H_v3_20261115_1001')]:
 d=BASE/f'{case}_v4_20261115_1050'; zp=d/f'{case}_v4_result.zip';assert zp.exists() and OUT!=zp
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None
  manifest=json.loads(z.read('sha256.json'))
  assert set(manifest)==set(z.namelist())-{'sha256.json'}
  assert all(digest(z.read(k))==v for k,v in manifest.items())
  get=lambda k:json.loads(z.read(k+'.json'))
  gate,exit_,pv,reg,vtk=get('geometry_gate'),get('solver_exit'),get('pointvalues'),get('iou_registration'),get('vtk_header_sha256')
  state=json.loads((d/'controller_state.json').read_text())
  oldzip=BASE/old/f'{case}_result.zip';assert oldzip.exists()
  with zipfile.ZipFile(oldzip) as oz: oldvtk=json.loads(oz.read('vtk_header_sha256.json'))
  assert exit_['exit']==0 and state['event']=='session_stopped' and state['CU_estimate']<=2
  assert vtk['vtk_sha256']==pv['source_vtk_sha256']==oldvtk['vtk_sha256']
  assert reg['selected_offset_xy_m']==pv['selected_offset_xy_m']==[2,2]
  assert len(pv['rows'])==len(pv['offset_0_2_rows'])==len(pv['zero_offset_rows'])==(195 if case=='BG_1H' else 200)
  assert [a['offset_xy_m'] for a in reg['aggregate']]==[[0,0],[2,0],[0,2],[2,2]]
  assert reg['aggregate'][2]['iou']==reg['aggregate'][3]['iou']
  log=z.read('solver.log').decode(errors='replace')
  assert str(step) in log
  run=z.read('run.log').decode(errors='replace')
  assert '554' in run or '554' in log
  first=['',f'## {case} — run, provenance, and registration','',f'Run root: `{d}`. Colab G4 (RTX PRO 6000 Blackwell), after the A100 allocation refusal documented in `controller.log`. Solver exit 0; {step:,} terminal steps, 554 time-mean samples, last {window:,} steps at stride {stride}. The native geometry gate executed before the full solver. Session creation-before-to-confirmed-stop {state["elapsed_session_s"]:.3f} s, conservative assumed tariff {state["rate_CU_per_hour_conservative"]:.2f} CU/h, estimated {state["CU_estimate"]:.6f} CU (not an invoiced debit; failed A100 allocation before VM creation excluded). Owned session stopped at {state["timestamp"]}.', '',f'Native gate: ground wall label {gate["ground_wall_label_m"]:g} m; low-roof solid samples {gate["low_roof_sample_count"]}, tower-roof samples {gate["tower_roof_sample_count"]}, floating count {gate["floating"]}. PASS means these script checks passed, not experimental wind accuracy.','', '### Individually checked building roofs','', '| Building | Base solid cells | 20 m roof cells | 60 m roof cells | Solid cells above roof |','|---:|---:|---:|---:|---:|']
  for b in reg['per_building']:first.append(f'| {b["building"]} | {b["base_solid_cells"]} | {b["roof_20m_cells"]} | {b["roof_60m_cells"]} | {b["above_roof_solid_cells"]} |')
  first+=['', 'The 1H check covers nine 20 m roofs; the 3H check covers eight 20 m roofs and the one 60 m roof.','', 'C38 full-scale x is downwind (+x), y transverse (+y), z upward (+z). Signed time-mean u,v,w are in m/s. VTK origin '+str(vtk['origin_xyz_m'])+', spacing '+str(vtk['spacing_xyz_m'])+' m. S1 uses C38 height above effective 1 m ground-wall label; `clamped` and positive-weight solid corners are flagged. U_H=3.1 m/s at H=20 m; speed/U_H=sqrt(<u>²+<v>²+<w>²)/U_H, not <|u|>/U_H. Both source and sampled coordinates are retained.','', '### IoU registration independent of wind observations','',f'Levels: {", ".join(str(x) for x in reg["levels_m"])} m. Aggregate IoU is sum(intersections)/sum(unions), not a fit to measured speeds.','', '| offset (x,y) m | intersection | union | aggregate IoU |','|---|---:|---:|---:|']
  for a in reg['aggregate']:first.append(f'| ({xyz(a["offset_xy_m"])}) | {a["intersection"]} | {a["union"]} | {a["iou"]:.9f} |')
  first+=['','(0,2) and (2,2) tie on aggregate IoU. The frozen per-axis positive-centroid-direction tie rule chooses (2,2); IoU alone does not uniquely determine x. Per-height candidates and building-roof counts are in the verified ZIP `iou_registration.json`.','']
  lists=[]
  for label,key in [('Selected (2,2)','rows'),('Alternative (0,2)','offset_0_2_rows'),('Unregistered (0,0)','zero_offset_rows')]:
   mixed=[f'{r["kind"]}/{r["id"]}' for r in pv[key] if r['solid_weight']>0]
   lists.append(f'{label} positive-weight solid-support IDs ({len(mixed)}): '+(', '.join(mixed) if mixed else 'none')+'.')
  first+=lists+['Any solid-support extraction is NOT a fluid velocity; a zero is NOT a still-air prediction and must not enter an unobstructed flow-site comparison.','', '### Mean-field, evidence and hashes','',f'- v4 archive: `{zp}`; SHA256 `{digest(zp.read_bytes())}`. ZIP CRC and all {len(manifest)} embedded member SHA256 entries verified.',f'- v3 archive: `{oldzip}`; SHA256 `{digest(oldzip.read_bytes())}`.',f'- Remote mean VTK SHA256: `{vtk["vtk_sha256"]}`; v3 remote mean VTK SHA256: `{oldvtk["vtk_sha256"]}`. Exact reported hash equality for these same-seed mean fields; the full VTK was not copied locally.','']
  for k,v in sorted(manifest.items()):first.append(f'- ZIP member `{k}` SHA256: `{v}`')
  comp=vtk['comparison']; first+=['',f'- Measured inlet 2 m speed: {comp[next(k for k in comp if k.startswith("inlet_x"))]:.6f} m/s; four archived open-ground 2 m speeds: {", ".join(fmt(x) for x in comp["open_agl2_speeds_mps"])} m/s; four-column mean/inlet ratio {comp["open_mean_to_inlet_ratio"]:.6f}. These columns are not all upstream. AF 2 m comparison is not defined for this BG archive.','', '### Registered main points alongside (0,2) and (0,0) sensitivities','', '| Kind | ID | Zone | C38 x,y,z (m) | LUW x,y,z (m), (2,2) | AGL (m) | (2,2) u,v,w (m/s) | (2,2) speed/U_H | (0,2) u,v,w (m/s) | (0,2) speed/U_H | (0,0) u,v,w (m/s) | (0,0) speed/U_H | solid weights (2,2)/(0,2)/(0,0) |','|---|---:|---|---|---|---:|---|---:|---|---:|---|---:|---|']
  for a,b,c in zip(pv['rows'],pv['offset_0_2_rows'],pv['zero_offset_rows']):
   assert (a['kind'],a['id'],a['c38_xyz_m'])==(b['kind'],b['id'],b['c38_xyz_m'])==(c['kind'],c['id'],c['c38_xyz_m'])
   def vec(r):return ', '.join(fmt(r[x+'_mps']) for x in 'uvw')
   first.append(f'| {a["kind"]} | {a["id"]} | {a["zone"]} | {xyz(a["c38_xyz_m"])} | {xyz(a["luw_sample_xyz_m"])} | {a["actual_agl_m"]:g} | {vec(a)} | {fmt(a["speed_over_UH"])} | {vec(b)} | {fmt(b["speed_over_UH"])} | {vec(c)} | {fmt(c["speed_over_UH"])} | {a["solid_weight"]:.3f}/{b["solid_weight"]:.3f}/{c["solid_weight"]:.3f} |')
  parts+=first
assert not OUT.exists(), 'Do not overwrite an existing report'
OUT.write_text('\n'.join(parts)+'\n')
print('OUT',OUT,'SHA256',digest(OUT.read_bytes()),'bytes',OUT.stat().st_size)
