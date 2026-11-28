from pathlib import Path
from zipfile import ZipFile
import json,hashlib,math,statistics
B=Path(__file__).resolve().parents[2]
R=Path(__file__).resolve().parent
A=R/'CaseD_retry6_20261115_0411'; C=R/'CaseD_retry9_20261115_0756'
O=B/'04_Handoffs/C38.2_caseD_bg_pointvalues_draft_v2_20261115.md'
assert not O.exists()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def load(p):
 with ZipFile(p) as z:
  assert z.testzip() is None
  ledger=json.loads(z.read('sha256.json'))
  assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in ledger.items())
  return json.loads(z.read('pointvalues.json'))
a=load(A/'caseD_result.zip'); c=load(C/'caseD_result.zip')
ra={(r['kind'],str(r['id'])):r for r in a['rows']}; rc={(r['kind'],str(r['id'])):r for r in c['rows']}
assert len(ra)==len(rc)==99 and ra.keys()==rc.keys()
for key in ra:
 assert ra[key]['c38_xyz_m']==rc[key]['c38_xyz_m'] and ra[key]['luw_sample_xyz_m']==rc[key]['luw_sample_xyz_m']
def speed(r):return math.sqrt(sum(r[k]**2 for k in ('u_mps','v_mps','w_mps')))
diff={key:abs(speed(rc[key])-speed(ra[key])) for key in ra}
component={k:[abs(rc[key][k]-ra[key][k]) for key in ra] for k in ('u_mps','v_mps','w_mps','speed_over_UH')}
state=json.loads((C/'controller_state.json').read_text())
prof=json.loads((C/'diagnostic_evidence/profiles_open_streets.json').read_text()); inlet=json.loads((C/'diagnostic_evidence/profiles_upstream.json').read_text())
print('profile first',inlet[0])
openrows=[q for q in prof if q['group']=='open' and q['height_agl_m'] in (2,3,5,10)]
assert len(openrows)==16 and len({(q['x_m'],q['y_m']) for q in openrows})==4
in2=[q for q in inlet if q['x_m']==2 and q['y_m']==550 and q['height_agl_m']==2];assert len(in2)==1
report={'n':len(ra),'max_abs_speed_mps':max(diff.values()),'mean_abs_speed_mps':statistics.mean(diff.values()),'mean_signed_speed_mps':statistics.mean(speed(rc[k])-speed(ra[k]) for k in ra),'max_id':max(diff,key=diff.get),'component_abs':{k:{'max':max(v),'mean':statistics.mean(v)} for k,v in component.items()},'inlet_measured_mps':in2[0]['speed_mps'],'inlet_ratio_AF':in2[0]['speed_mps']/3.833,'open_rows':openrows,'sha256':{'retry6':sha(A/'caseD_result.zip'),'retry9':sha(C/'caseD_result.zip'),'profiles_open':sha(C/'diagnostic_evidence/profiles_open_streets.json'),'profiles_inlet':sha(C/'diagnostic_evidence/profiles_upstream.json')}}
assert all(math.isfinite(x) for x in (report['max_abs_speed_mps'],report['mean_abs_speed_mps']))
(R/'caseD_v2_comparison.json').write_text(json.dumps(report,indent=2))
lines=['# AIJ Case D: LUW round-9 2 m S1 per-point draft v2 (2026-11-15)','','Status: draft for LUW Lead review only; not released to C38.2. Case D only. The reported speed is the magnitude of the time-mean velocity vector, not the time mean of instantaneous scalar speed.','','## Run and sampling definition','',f"Colab G4 (NVIDIA RTX PRO 6000 Blackwell Server Edition); 33,767 steps, 553 time-mean samples. Prescribed terminal window: last 23,215 steps, stride 42 (rounded from the Case A H/U_H scaling). Mean VTK: `{c['source_vtk']}`. One time-mean field, no temporal splice; physical averaging duration was not independently verified.",'',f"C38 full-scale coordinates: x along incoming wind (+x), y lateral, z up (m); x_LUW=x_C38+850 m, y_LUW=y_C38+550 m. Native VTK origin {c['origin_xyz_m']} m, spacing {c['spacing_xyz_m']} m. Signed time-mean u,v,w are +x,+y,+z components (m/s). U_H={c['UH_mps']} m/s is the nominal Case D inlet/reference velocity at H={c['UH_height_m']} m; speed/U_H=|<u,v,w>|/U_H. This is not <|u|>/U_H.",'',f"S1: measurement height is above the effective open-ground wall (VTK label {c['wall_label_m']} m, midway between the highest solid and first fluid centre). The LUW sample label is wall label plus C38 height. Below-first-fluid samples are clamped and flagged; positive-weight solid interpolation corners are listed as mixed. This archive reports {c['clamped']} clamped and {c['mixed']} mixed of {len(rc)} points. Native ground/building gate: geometry_gate.json in the retry9 archive.",'',f"Creation-call-to-confirmed-stop duration {state['elapsed_session_s']:.3f} s; estimated {state['CU_estimate']:.6f} CU using an assumed conservative {state['rate_CU_per_hour_conservative']:.2f} CU/h. GPU-specific tariff was not verified; neither an actual debit nor an isolated account charge is claimed.",'','## A100 versus RTX PRO 6000 pointwise consistency','',f"Identical keyed C38 and sampled LUW coordinates for all {len(rc)} group/ID points. Defining d_i=| |<u_i>_retry9| - |<u_i>_retry6| | (m/s), max d_i={report['max_abs_speed_mps']:.9f} m/s (group/ID {report['max_id']}), mean d_i={report['mean_abs_speed_mps']:.9f} m/s; mean signed retry9-minus-retry6 speed={report['mean_signed_speed_mps']:.9f} m/s. These are independent time-averaged turbulent runs; nonzero point differences cannot be ascribed solely to GPU hardware. The aggregate comparison is quantitative, not bitwise identity.",'',f"Component absolute differences (max/mean m/s): u {component['u_mps'] and report['component_abs']['u_mps']['max']:.9f}/{report['component_abs']['u_mps']['mean']:.9f}; v {report['component_abs']['v_mps']['max']:.9f}/{report['component_abs']['v_mps']['mean']:.9f}; w {report['component_abs']['w_mps']['max']:.9f}/{report['component_abs']['w_mps']['mean']:.9f}.",'','## Near-ground limitation','',f"At inlet x=2 m, y=550 m, measured |<u>| at 2 m AGL={report['inlet_measured_mps']:.9f} m/s; AF-prescribed 2 m value=3.833 m/s; measured/prescribed={report['inlet_ratio_AF']:.6f}. These are distinct quantities.",'','Four designated open-ground columns, measured |<u>| (m/s) at 2, 3, 5, 10 m AGL (not building-street observations):','','| LUW x,y (m) | 2 m | 3 m | 5 m | 10 m |','|---|---:|---:|---:|---:|']
for x,y in sorted({(q['x_m'],q['y_m']) for q in openrows}):
 vals={q['height_agl_m']:q['speed_mps'] for q in openrows if q['x_m']==x and q['y_m']==y}
 lines.append(f"| {x}, {y} | {vals[2]:.6f} | {vals[3]:.6f} | {vals[5]:.6f} | {vals[10]:.6f} |")
meanopen=statistics.mean(q['speed_mps'] for q in openrows if q['height_agl_m']==2)
lines+=['',f"Mean open-ground 2 m speed / measured inlet 2 m speed = {meanopen:.9f}/{report['inlet_measured_mps']:.9f} = {meanopen/report['inlet_measured_mps']:.6f}. In this configuration (2 m grid, flat-ground no-slip bounce-back and no wall model), the 2 m velocity drops to roughly half the inlet before the building measurement sites. The 2 m point values therefore do not measure LBM accuracy under an adequate near-wall treatment. This observational pattern supports substantial near-ground attenuation in this run; it does not uniquely isolate the wall operator from inflow, turbulence and other boundary effects.",'','## SHA256 provenance','']
for k,v in report['sha256'].items(): lines.append(f'- {k}: {v}')
lines.append(f"- Remote average VTK: {c['source_vtk_sha256']} (header and hash archived; full VTK not locally retained).")
with ZipFile(C/'caseD_result.zip') as z:
 ledger=json.loads(z.read('sha256.json'))
for name,h in sorted(ledger.items()):lines.append(f'- retry9 archive member `{name}`: {h}')
lines+=['','## Per-point time-mean velocities','','C38 and LUW coordinates in metres. S/T retain source labels, including shared physical locations. Full precision in retry9 pointvalues.json; display values rounded.','','| Group | ID | C38 x,y,z (m) | LUW sample x,y,z (m) | Actual AGL (m) | u (m/s) | v (m/s) | w (m/s) | speed/U_H | Clamped | Mixed |','|---|---:|---|---|---:|---:|---:|---:|---:|---|---|']
for r in c['rows']:
 xyz=lambda key:', '.join(f'{v:.3f}' for v in r[key])
 lines.append(f"| {r['kind']} | {r['id']} | {xyz('c38_xyz_m')} | {xyz('luw_sample_xyz_m')} | {r['actual_agl_m']:.3f} | {r['u_mps']:.9f} | {r['v_mps']:.9f} | {r['w_mps']:.9f} | {r['speed_over_UH']:.9f} | {'yes' if r['clamped'] else 'no'} | {len(r['solid_corners'])} |")
lines+=['','The Markdown SHA256 is reported in the handoff, not self-embedded.','']
O.write_text('\n'.join(lines));print('REPORT',O,sha(O),'COMP',report['max_abs_speed_mps'],report['mean_abs_speed_mps'])
