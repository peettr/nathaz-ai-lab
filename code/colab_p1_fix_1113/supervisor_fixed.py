#!/usr/bin/env python3
"""Fail-closed smoke gate; only then launch the preregistered full P1 batch."""
import json, os, subprocess, sys, time, traceback
from pathlib import Path

C=Path('/content'); RESULT=C/'a170_2'/'results'; LOG=C/'a170_2_supervisor.log'
ENV=os.environ.copy()
ENV.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')

def run(mode):
    with (C/f'a170_2_{mode}.log').open('a') as fh:
        return subprocess.run([sys.executable,'-u','/content/colab_a170_2.py',mode],
                              cwd=C,env=ENV,stdout=fh,stderr=subprocess.STDOUT).returncode

def main():
    rc=run('smoke')
    assert rc==0 and (C/'a170_2_smoke.done').exists(), f'smoke exit={rc}'
    expected=['G1','G2','G2Lc']; rows={}
    for g in expected:
        p=RESULT/f'P1_power_s1301_{g}.json'; x=json.loads(p.read_text())
        rows[g]={'returncode':x['returncode'],'yaw_rate_max_deg_s':x['yaw_rate_max_deg_s'],
                 'start_abs_s':x['start_abs_s'],'tstart_output_s':0.0}
        assert x['returncode']==0 and x['yaw_rate_max_deg_s']<=.31, (g,rows[g])
        # Check the first-second ES time span directly rather than trusting TStart input.
        root=Path('/content/a170_2/runs')/f'run_P1_power_s1301_{g}'
        from sys import path
        path.insert(0,'/content/a170_2/code')
        from analyze_segment_b import read_out
        d=read_out(root/'NREL-5MW.out',['Time','NacYaw'])
        t=d['Time']; assert t[0]<.1 and t[-1]>1.1,(g,t[0],t[-1])
        rows[g]['tstart_output_s']=float(t[0]);rows[g]['first_second_yaw_delta_deg']=float(
            __import__('numpy').interp(1.,t,d['NacYaw'])-__import__('numpy').interp(0.,t,d['NacYaw']))
    provenance=json.loads(Path('/content/a170_2/runs/P1_power_s1301/provenance.json').read_text())
    assert provenance['prepeak_window_abs_s']==[2018.,2078.]
    assert abs(provenance['prepeak60_mean_speed_mps']-16.038876662713623)<1e-5
    status={'status':'passed','smoke':rows,'provenance':provenance,'checked_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
    (C/'a170_2_smoke_gate.json').write_text(json.dumps(status,indent=2))
    print('SMOKE_GATE_PASS',json.dumps(rows),flush=True)
    rc=run('full')
    assert rc==0 and (C/'a170_2_full.done').exists(),f'full exit={rc}'
    print('FULL_DONE',flush=True)

if __name__=='__main__':
    try: main()
    except BaseException:
        tb=traceback.format_exc();print(tb,flush=True)
        (C/'a170_2_supervisor.failed').write_text(tb)
        if not (C/'a170_2_smoke_gate.json').exists():
            (C/'a170_2_smoke_gate.json').write_text(json.dumps({'status':'failed','traceback':tb},indent=2))
        sys.exit(1)
    finally:
        (C/'a170_2_campaign.done').write_text('supervisor exited; inspect full.done or supervisor.failed\n')
