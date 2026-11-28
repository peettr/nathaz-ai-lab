#!/usr/bin/env python3
"""L22.6 T03 v3.3 汇总（Lead 11-27）。读每根 metrics.json，输出 csv：
- 新增 max_dir_err_deg = max_z direction_abs_error_deg（准备 2：补导出风向）
- e_Ly_v33：可用（非删失）高度 <3 个记 None（准备 3：E2 删失规则，v3.1 第 141 行）
- 逐位查重：五项指标完全相同的行标 dup_of（准备 4）
用法：aggregate_v33.py <metrics 根目录> <out.csv>"""
import json,glob,os,sys,csv,math
root,out=sys.argv[1],sys.argv[2]
rows=[]
for f in sorted(glob.glob(os.path.join(root,'L22_6_v3S0_REC_*','metrics.json'))):
    tag=os.path.basename(os.path.dirname(f)).replace('L22_6_v3S0_REC_','').rsplit('_',1)[0]
    g,s=tag.rsplit('_',1); d=json.load(open(f)); H=d['heights']
    dirs=[h['direction_abs_error_deg'] for h in H.values() if h.get('direction_abs_error_deg') is not None]
    ely=[h['e_Ly_local_x'] for h in H.values() if h.get('e_Ly_local_x') is not None and math.isfinite(h['e_Ly_local_x'])]
    rows.append(dict(group=g,seq=s,max_dir_err_deg=max(dirs) if len(dirs)==len(H) else None,
        max_speed_in=d['max_speed_in'],max_diag_in=d['max_diag_in'],max_rho_in=d['max_rho_in'],
        rho_xz_z15=d['rho_xz_z15_signed_input_delta'],e_Ly_raw=d['e_Ly'],n_Ly_heights=len(ely),
        e_Ly_v33=(max(ely) if len(ely)>=3 else None)))
key=lambda r:tuple(repr(r[k]) for k in ('max_speed_in','max_diag_in','max_rho_in','rho_xz_z15','e_Ly_raw'))
first={}
for r in rows:
    k=key(r); r['dup_of']=first.get(k,''); first.setdefault(k,r['group']+'_'+r['seq'])
with open(out,'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
dups=[r for r in rows if r['dup_of']]
print(len(rows),'rows;',len(dups),'duplicates:',[(r['group']+'_'+r['seq'],r['dup_of']) for r in dups])
sys.exit(2 if dups else 0)
