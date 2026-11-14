#!/usr/bin/env python3
"""Format CRC T03 metrics into small local B0 target-deviation CSV and B1 summary.
No scientific recomputation: only arithmetic on the CRC-generated small JSON.
"""
import csv,json,sys
from pathlib import Path
p=Path(sys.argv[1]); out=Path(sys.argv[2]); d=json.loads(p.read_text())
with (out/'template/B0_target_deviation.csv').open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['z_m','input_U_mps','B0_Ux_mps','U_relative_diff','input_Rxx','B0_Rxx','Rxx_relative_diff','input_Ryy','B0_Ryy','Ryy_relative_diff','input_Rzz','B0_Rzz','Rzz_relative_diff','input_Lx_u_m','B0_Lx_u_m','Lx_u_relative_diff','Lx_u_censored','input_Ly_u_m','B0_Ly_u_m','Ly_u_relative_diff','Ly_u_censored','data_source'])
    for z,t in d['target'].items():
        b=d['B0']['heights'][z]; r=b['R_local']; lx=b['Lx_local']['x']; ly=b['Ly_local']['x']
        def rel(x,y): return (x/y-1) if x is not None and y else ''
        w.writerow([z,t['U'],b['mean_global_mps'][0],rel(b['mean_global_mps'][0],t['U']),t['R']['xx'],r['xx'],rel(r['xx'],t['R']['xx']),t['R']['yy'],r['yy'],rel(r['yy'],t['R']['yy']),t['R']['zz'],r['zz'],rel(r['zz'],t['R']['zz']),t['L_matrix'][0][0],lx['value_m'],rel(lx['value_m'],t['L_matrix'][0][0]),lx['censored'],t['L_matrix'][1][0],ly['value_m'],rel(ly['value_m'],t['L_matrix'][1][0]),ly['censored'],'E7 TInF upstream 8737a0d5; CRC 1600473/1600525'])
with (out/'B1_scores.csv').open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['z_m','target_psi_deg','measured_psi_deg','abs_direction_error_deg','Rxx_relative_to_B0','Rxy_relative_to_B0','Rxz_relative_to_B0','Ryy_relative_to_B0','Ryz_relative_to_B0','Rzz_relative_to_B0','Lx_u_relative_to_B0','Ly_u_relative_to_B0','Lx_u_censored','Ly_u_censored','data_source'])
    for z,v in d['B1_vs_B0'].items():
        h=d['B1']['heights'][z]; rr=v['R_relative_delta']; sc=v['scale_relative_delta']; w.writerow([z,h['target_psi_deg'],h['mean_direction_deg'],v['direction_abs_error_deg']]+[rr[k] for k in ('xx','xy','xz','yy','yz','zz')]+[sc['Lx_local']['x']['relative_delta'],sc['Ly_local']['x']['relative_delta'],sc['Lx_local']['x']['censored'],sc['Ly_local']['x']['censored'],'E7 TInF upstream 8737a0d5; CRC 1600473/1600525'])
print(out/'template/B0_target_deviation.csv',out/'B1_scores.csv')
