#!/usr/bin/env python3
"""Colab CPU-only: stage pinned r2 turbine; two D420 diagnostic BTS smoke runs."""
import json,os,sys,tarfile,gzip,shutil,subprocess,time,traceback,hashlib
from pathlib import Path
R=Path('/content/a170_2_interface');R.mkdir(exist_ok=True)

def save(name,object): (R/name).write_text(json.dumps(object,indent=2)+'\n')
def main():
    import numpy as np
    from cm1_to_bts import main as convert
    with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as tf:tf.extractall(R,filter='data')
    (R/'bin').mkdir(exist_ok=True)
    with gzip.open('/content/openfast_5_linux_1014.gz','rb') as src,(R/'bin/openfast').open('wb') as dst:shutil.copyfileobj(src,dst)
    (R/'bin/openfast').chmod(0o755)
    sys.path.insert(0,str(R/'code'))
    import segment_a_run as a,segment_b_run as b
    from analyze_segment_b import read_out
    b.BASE=R/'base';b.ROOT=R/'runs';b.SRC=R/'base/ff_smoke_feedback';b.FAST=R/'bin/openfast';b.LIB=R/'base/rosco210_ff_build_guo_v2/libdiscon.so'
    b.ROOT.mkdir(exist_ok=True)
    sys.path.insert(0,'/content')
    source='/content/d420_subwindow_source.npz'
    import cm1_to_bts
    for kind in ('power','wood'):
        print('CONVERT',kind,flush=True)
        sys.argv=['cm1_to_bts.py',source,str(R/kind),'--profile',kind,'--seed','112']
        convert()
    rows=[]
    for kind,position in (('power','near_geometric'),('wood','offset_geometric')):
        root=R/kind;src=root/(position+'_'+kind+'.bts')
        wroot=R/'runs'/f'{kind}_{position}';wroot.mkdir(exist_ok=False)
        (wroot/'wind.bts').symlink_to(src)
        row={'case':kind,'seed':112,'group':position,'source':str(wroot),'start_abs_s':0.,'end_abs_s':65.,'trigger_abs_s':500.}
        dest=b.stage(row)
        a.replace_key(dest/'NREL-5MW.fst','TMax','65.0')
        a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
        a.replace_key(dest/'NREL-5MW.fst','OutFmt','"ES20.12E3"')
        a.replace_key(dest/'NREL-5MW.fst','TStart','0.0')
        a.replace_discon(dest/'DISCON.IN','Y_Rate',f'{np.deg2rad(.24):.10f}')
        # Diagnostic only: prevent precomputed shutdown, so smoke verifies inflow and structural time integration.
        a.replace_discon(dest/'DISCON.IN','SD_EnableTime','0')
        a.replace_discon(dest/'DISCON.IN','SD_Time','9999.0')
        env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(R/'base/segment_a_v4_curve.txt'),ROSCO_FF_GAIN_DEG_PER_MS='0',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        print('FAST_START',kind,position,flush=True);start=time.monotonic()
        with (dest/'openfast.log').open('w') as log:
            try: rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
            except subprocess.TimeoutExpired:rc=-999
        out=dest/'NREL-5MW.out'
        info={'profile':kind,'position':position,'returncode':rc,'wall_s':round(time.monotonic()-start,2),'bts_file':str(src),'bts_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'log_tail':(dest/'openfast.log').read_text(errors='replace')[-1800:]}
        if rc==0 and out.exists():
            try:
                d=read_out(out,['Time','Wind1VelX','Wind1VelY','NacYaw','RotSpeed'])
                info.update(final_time_s=float(d['Time'][-1]),n_samples=len(d['Time']),wind1_x_range_mps=[float(d['Wind1VelX'].min()),float(d['Wind1VelX'].max())],rotor_speed_max_rpm=float(d['RotSpeed'].max()),yaw_final_deg=float(d['NacYaw'][-1]))
                assert info['final_time_s']>=64.99
                # Check source BTS's original center series against OpenFAST Wind1VelX;
                # phase pad aligns t+7 lookup, except initial boundary interpolation.
                with np.load(root/(position+'_diagnostic.npz')) as z:
                    sample=np.interp(d['Time'],z['t_s'],z['hub_u'])
                info['hub_wind_rmse_mps']=float(np.sqrt(np.mean((sample-d['Wind1VelX'])**2)))
            except Exception as e:info['readback_error']=repr(e)
        rows.append(info);save('smoke_results.json',rows)
        print('FAST_END',kind,rc,info.get('final_time_s'),info.get('hub_wind_rmse_mps'),flush=True)
    assert len(rows)==2 and all(x['returncode']==0 and x.get('final_time_s',0)>=64.99 for x in rows)
    (R/'run.done').write_text('ok\n')
if __name__=='__main__':
    try:main()
    except Exception:
        (R/'run.failed').write_text(traceback.format_exc());traceback.print_exc();raise
