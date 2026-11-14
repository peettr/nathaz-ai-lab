#!/usr/bin/env python3
"""CRC full-duration three-arm smoke; scientific gate before any batch."""
import json, os, sys, traceback
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
import crc_a170_2 as m


def run():
    m.init()
    p=m.make_seed(1301,'power')
    rows=[m.row(1301,'power','G1',p['rotor_3s_first25_abs_s'])]
    results={}
    for row in rows:
        result=m.run_one(row)
        results[row['group']]=result
        m.checkpoint()
        if result['returncode'] != 0 or result['yaw_rate_max_deg_s'] > .31:
            raise RuntimeError(f"CRC smoke failed {row['group']}: rc={result['returncode']} rate={result.get('yaw_rate_max_deg_s')}")
    hit=m.g2lc_hit(1301,'power')
    for group,trigger in [('G2',p['g2_trigger_abs_s']),('G2Lc',hit)]:
        row=m.row(1301,'power',group,trigger)
        result=m.run_one(row)
        results[group]=result
        m.checkpoint()
        if result['returncode'] != 0 or result['yaw_rate_max_deg_s'] > .31:
            raise RuntimeError(f"CRC smoke failed {group}: rc={result['returncode']} rate={result.get('yaw_rate_max_deg_s')}")
    ref=Path(os.environ['A170_PACKAGE'])/'colab_reference'
    comparisons={}
    for group,record in results.items():
        prior=json.loads((ref/f'P1_power_s1301_{group}.json').read_text())
        comparisons[group]={k: {'colab':v, 'crc':record['metrics'].get(k),
                    'relative_difference_pct':100*(record['metrics'][k]-v)/abs(v) if v else None}
                    for k,v in prior['metrics'].items()}
        comparisons[group]['yaw_rate_max_deg_s']={'colab':prior['yaw_rate_max_deg_s'],
                    'crc':record['yaw_rate_max_deg_s']}
    output={'status':'passed','groups':{g:{'returncode':v['returncode'],'yaw_rate_max_deg_s':v['yaw_rate_max_deg_s'], 'wall_s':v['wall_s']} for g,v in results.items()},
            'colab_comparison_record_only':comparisons,'input':p}
    (m.P/'smoke_gate.json').write_text(json.dumps(output,indent=2))
    print('SMOKE_GATE_PASS',json.dumps(output['groups']),flush=True)

if __name__=='__main__':
    try:run()
    except BaseException:
        tb=traceback.format_exc();print(tb,flush=True)
        m.P.mkdir(parents=True,exist_ok=True)
        (m.P/'smoke.failed').write_text(tb)
        sys.exit(1)
