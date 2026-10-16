from pathlib import Path
import re,time
r=Path('/content/luw-aij-r4');p=r/'solver.log'
print('time',time.time(),'marker',(r/'solver.exit').read_text() if (r/'solver.exit').exists() else 'RUNNING','metrics',(r/'solver.metrics').read_text() if (r/'solver.metrics').exists() else 'missing')
if p.exists():
 s=p.read_text(errors='replace');s=re.sub(r'\x1b\[[0-9;]*m','',s).replace('\r','\n');lines=[x for x in s.splitlines() if any(w in x for w in ('Grid Resolution','GPU Estimate','Unit Conversion','Angle','Downstream BC','Required VRAM','steps/s','MLUPs','time step','step ','Error','error','Exception','Runtime','Device Memory','averag','GPU Memory','Peak'))];print('LOG_BYTES',p.stat().st_size,'LAST', '\n'.join(lines[-45:])[-12000:]);print('TAIL',s[-1500:])
