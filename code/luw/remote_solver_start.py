import pathlib,subprocess,os
r=pathlib.Path('/content/luw-aij'); repo=r/'repo'; case=repo/'examples/example_ProfileResearch_noDEM'; binary=repo/'core/cfd_core/FluidX3D/bin/FluidX3D'
assert binary.exists(); assert (case/'proj_temp/CaseE_PF.stl').exists()
code='''import subprocess,time,pathlib,os
r=pathlib.Path('/content/luw-aij'); repo=r/'repo'; case=repo/'examples/example_ProfileResearch_noDEM'; binary=repo/'core/cfd_core/FluidX3D/bin/FluidX3D'
t0=time.time(); (r/'solver.start').write_text(str(t0)); f=(r/'solver.log').open('w',buffering=1)
p=subprocess.Popen([str(binary),str(case/'conf.luwpf')],cwd=case,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
peak=0
while p.poll() is None:
 s=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
 try: peak=max(peak,int(s.stdout.strip().splitlines()[0]))
 except Exception: pass
 (r/'solver.metrics').write_text(f'elapsed_s={time.time()-t0:.1f} peak_gpu_memory_MiB={peak} pid={p.pid}\\n')
 time.sleep(5)
(r/'solver.exit').write_text(f'exit={p.returncode} wall_s={time.time()-t0:.2f} peak_gpu_memory_MiB={peak}\\n')
'''
(r/'solver_wrapper.py').write_text(code)
f=(r/'solver_wrapper.log').open('w'); p=subprocess.Popen(['python3',str(r/'solver_wrapper.py')],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('solver wrapper pid',p.pid,'case',case,'config', (case/'conf.luwpf').read_text(),flush=True)
