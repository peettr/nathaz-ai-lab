#!/usr/bin/env python3
"""Aggregate CRC-produced stage-0 raw metrics. Never infer missing jobs as zeros."""
import argparse,csv,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('submission',type=Path);p.add_argument('source_directory',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    rows=[]; seen=set()
    for line in a.submission.read_text().splitlines():
        x=json.loads(line); tag=x['group']; seq=x['seq']; key=(tag,seq)
        if key in seen: raise ValueError(f'duplicate group/seq {key}')
        seen.add(key)
        # Three 0.05-s debug jobs are not 120-s measurements. Keep them as
        # explicit unmeasured rows, never zero-fill or infer statistics.
        if tag=='DBG':
            rows.append({'group':tag,'seq':seq,'job_id':x['job_id'],
                         'status':'short_debug_not_measurement',
                         'max_speed_in':'','max_diag_in':'','max_rho_in':'',
                         'rho_xz_z15_signed_input_delta':'','e_Ly':'',
                         'censored_heights':''})
            continue
        # Each remote metrics JSON is copied unchanged after CRC SHA256 comparison.
        source=a.source_directory/(f'{tag}_{seq}.json')
        if not source.is_file(): raise FileNotFoundError(source)
        m=json.loads(source.read_text()); assert m['schema']=='L22_6_T03_stage0_raw_v3'
        rows.append({'group':tag,'seq':seq,'job_id':x['job_id'],
                     'status':'measured_120s',
                     'max_speed_in':m['max_speed_in'],'max_diag_in':m['max_diag_in'],
                     'max_rho_in':m['max_rho_in'],
                     'rho_xz_z15_signed_input_delta':m['rho_xz_z15_signed_input_delta'],
                     'e_Ly':m['e_Ly'],'censored_heights':m['censored_heights']})
    if len(rows)!=45 or sum(r['status']=='measured_120s' for r in rows)!=42:
        raise ValueError(f'expected 45 jobs with 42 measured and 3 debug; got {len(rows)} jobs')
    if a.output.exists(): raise FileExistsError(a.output)
    with a.output.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({'path':str(a.output),'rows':len(rows)}))
if __name__=='__main__':main()
