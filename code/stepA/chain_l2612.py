# Lead 11-03: chain after extraction: SAE -> (correlation controls on CPU || interventions on GPU)
import subprocess,time,os
from pathlib import Path
R=Path('/content/l2612-stepA'); L=open(R/'chain.log','a')
def say(m): L.write(time.strftime('%H:%M:%S ')+m+'\n'); L.flush()
while not (R/'extract.done').exists(): time.sleep(20)
say('extract.done='+(R/'extract.done').read_text().strip())
if (R/'extract.done').read_text().strip().startswith('ok'):
    r=subprocess.run(['python','/content/l2612-stepA/train_sae_v2.py'],cwd=R,stdout=open(R/'sae.log','a'),stderr=subprocess.STDOUT); say(f'sae rc={r.returncode}')
    if r.returncode==0:
        b=subprocess.Popen(['python','/content/l2612-stepA/b_controls.py'],cwd=R,stdout=open(R/'b.log','a'),stderr=subprocess.STDOUT)
        i=subprocess.run(['python','/content/l2612-stepA/intervene_v2.py'],cwd=R,stdout=open(R/'intervene.log','a'),stderr=subprocess.STDOUT); say(f'intervene rc={i.returncode}')
        b.wait(); say(f'b rc={b.returncode}')
(R/'chain.done').write_text('ok\n'); say('chain done')
