import csv,json,statistics
from pathlib import Path
r=Path(__file__).resolve().parent
short=json.loads((r/'gate_profiles.json').read_text())['rows']
base=json.loads((r.parents[1]/'wp1b_ibm/resolution_crop_v2/C1v2_offset_samples.json').read_text())['profiles']
base={int(x['z_agl']):x for x in base if x['x']==5.0}
full=json.loads((r.parents[1]/'wp1b_ibm/resolution_c05/C05_offset_samples_a_r10.json').read_text())['profiles']
full={int(x['z_agl']):x for x in full if x['x']==5.0}
rows=[]
for x in short:
 z=x['z'];b=base[z];f=full[z];rows.append({'z_m':z,'C1v2_U':b['U_mps'],'C1v2_k':b['k_m2s2'],'C05_original_full_U':f['U_mps'],'C05_original_full_k':f['k_m2s2'],'C05k_gate_U':x['U_mps'],'C05k_gate_k':x['k_m2s2'],'gate_rel_U':x['U_mps']/b['U_mps']-1,'gate_rel_k':x['k_m2s2']/b['k_m2s2']-1,'C05_full_rel_U':f['U_mps']/b['U_mps']-1,'C05_full_rel_k':f['k_m2s2']/b['k_m2s2']-1})
with (r/'inlet_gate_30.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
print('n',len(rows),'gate U max',max(abs(x['gate_rel_U']) for x in rows),'gate k max',max(abs(x['gate_rel_k']) for x in rows),'gate pass',all(abs(x['gate_rel_U'])<=.1 and abs(x['gate_rel_k'])<=.1 for x in rows),'full C05 Umax',max(abs(x['C05_full_rel_U']) for x in rows),'full C05 kmax',max(abs(x['C05_full_rel_k']) for x in rows))
print('gate fail U', [x['z_m'] for x in rows if abs(x['gate_rel_U'])>.1]);print('gate fail k',[x['z_m'] for x in rows if abs(x['gate_rel_k'])>.1]);print('full C05 fail U',[x['z_m'] for x in rows if abs(x['C05_full_rel_U'])>.1]);print('full C05 fail k',[x['z_m'] for x in rows if abs(x['C05_full_rel_k'])>.1])
