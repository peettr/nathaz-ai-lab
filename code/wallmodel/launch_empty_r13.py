"""Launch one immutable empty-field LUW variant with log and exit marker."""
import pathlib,subprocess,os
v=os.environ['EMPTY_VARIANT'];assert v in ('off','on')
r=pathlib.Path('/content/luw_wall_empty_r13');lock=r/f'{v}.lock';lock.open('x').close()
code='''import pathlib,subprocess,time,sys
r=pathlib.Path('/content/luw_wall_empty_r13');v=sys.argv[1];t=time.monotonic()
case=r/('case_'+v);exe=r/('solver_'+v)/'bin/FluidX3D'
with (r/f'solver_{v}.log').open('w',buffering=1) as log:
 p=subprocess.Popen([str(exe),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 p.wait();(r/f'{v}.exit').write_text(f'exit={p.returncode} wall_s={time.monotonic()-t:.2f}\\n')
'''
script=r/f'wrapper_{v}.py';script.write_text(code)
with (r/f'wrapper_{v}.log').open('w') as out:p=subprocess.Popen(['python3',str(script),v],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',v,p.pid,flush=True)
