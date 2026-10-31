#!/usr/bin/env python3
"""Expand frozen T03 B0 input-vs-observed deviations to all six R and six x/y scales."""
import csv,json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text()); out=Path(sys.argv[2])
comps=('xx','xy','xz','yy','yz','zz'); xyz=('x','y','z')
with out.open('w',newline='') as fh:
    w=csv.writer(fh)
    columns=['z_m','input_U_mps','B0_Ux_mps','U_relative_diff']
    for k in comps: columns += [f'input_R{k}',f'B0_R{k}',f'R{k}_relative_diff',f'R{k}_near_zero_denominator']
    for direction in ('x','y'):
        for i in xyz: columns += [f'input_L{direction}_{i}_m',f'B0_L{direction}_{i}_m',f'L{direction}_{i}_relative_diff',f'L{direction}_{i}_censored']
    w.writerow(columns+['data_source'])
    for z,t in d['target'].items():
        b=d['B0']['heights'][z]
        def rel(v,base): return (v-base)/abs(base) if v is not None and abs(base)>1e-12 else ''
        row=[z,t['U'],b['mean_global_mps'][0],rel(b['mean_global_mps'][0],t['U'])]
        for k in comps:
            v=t['R'][k]; obs=b['R_local'][k]
            diag=(t['R']['xx']*t['R']['yy'])**.5 if k=='xy' else (t['R']['xx']*t['R']['zz'])**.5 if k=='xz' else (t['R']['yy']*t['R']['zz'])**.5 if k=='yz' else abs(v)
            row += [v,obs,rel(obs,v),abs(v)<.05*diag]
        for direction,axis in (('x',0),('y',1)):
            for i,comp in enumerate(xyz):
                v=t['L_matrix'][axis][i]; got=b['L'+direction+'_local'][comp]
                row += [v,got['value_m'],rel(got['value_m'],v),got['censored']]
        w.writerow(row+['E7 TInF upstream 8737a0d5; CRC 1600473/1600525'])
print(out)
