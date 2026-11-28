from pathlib import Path
p=Path(__file__).parent/'worker_native.py';t=p.read_text()
def change(a,b):
 global t
 assert t.count(a)==1,(a,t.count(a));t=t.replace(a,b)
change("GROUPS=('K1a','K1b','K2','K3a','K3b');SEEDS=('1',)","GROUPS=('K3a','K3b');SEEDS=('1',)")
change("for group in ('B0',)+GROUPS:","for group in GROUPS:")
start=t.index('  # C-0 uses the already native-compiled K3a')
t=t[:start]+'''  # Actual GPU OpenCL compilation and at least 10 completed solver steps for BOTH variants.
  for group in GROUPS:
   check=OUT/(group+'_compilecheck');check.mkdir()
   src=exes[group][1]; log=OUT/(group+'_opencl_compilecheck.log')
   env={**os.environ,'T17_B_MODE':'compilecheck','T17_B_DIR':str(check),
        'T17_B_SEED':'1','T17_STAGE_A_ALLOW':'1',
        'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   with log.open('x') as f:
    rc=subprocess.run([str(exes[group][0])],cwd=src,env=env,stdout=f,
      stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=600).returncode
   seal(log)
   text=log.read_text(errors='replace')
   if rc!=0 or 'OpenCL C code successfully compiled' not in text or not(check/'producer.done').exists() or int((check/'producer.done').read_text().strip())<10:
    raise RuntimeError('OpenCL GPU compile/10 step failed '+group+' rc='+str(rc))
   print('OPENCL_NATIVE_10_STEPS',group,sha(log),flush=True)
''' + t[start:]
change("order=tuple((g,'1') for g in (('K1a','K1b','K2','K3a','K3b') if c0_pass else ('K1a','K1b','K2')))","order=tuple((g,'1') for g in GROUPS) if c0_pass else ()")
change("'expected':list(label+'_s1' for label,_ in order)","'expected':list(g+'_s'+seed for g,seed in order)")
# Preserve C-0 failure as an explicit gate, no K3 case solve.
p.write_text(t)
print('adapted worker',p)
