import subprocess,pathlib,os
r=pathlib.Path('/content/L26_18_v3')
assert all((r/x).exists() for x in ['run_bc_v3.py','calc_sar_bc_v3.py','selected_storm_scenes.csv','eye_scenes_x_sfmr_flights.csv'])
assert not (r/'launched').exists(), 'already launched'
(r/'launched').write_text('once')
cmd='OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python /content/L26_18_v3/run_bc_v3.py > /content/L26_18_v3/worker.log 2>&1; printf "%s\\n" "$?" > /content/L26_18_v3/exitcode'
p=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('WORKER_PID',p.pid)
