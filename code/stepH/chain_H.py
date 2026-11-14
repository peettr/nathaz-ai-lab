# L26.12 出路 H 接力（Lead 11-10）：staging -> b_controls_H (CPU, 后台) || intervene_H (GPU)
import subprocess,time
from pathlib import Path
O=Path('/content/l2612-stepH');O.mkdir(exist_ok=True);L=open(O/'chain.log','a')
def say(m):L.write(time.strftime('%H:%M:%S ')+m+'\n');L.flush()
r=subprocess.run(['python','/content/l2612-stepH/stage_H.py'],stdout=open(O/'stage.out','a'),stderr=subprocess.STDOUT);say(f'stage rc={r.returncode}')
if r.returncode==0:
    b=subprocess.Popen(['python','/content/l2612-stepH/b_controls_H.py'],stdout=open(O/'b.log','a'),stderr=subprocess.STDOUT)
    i=subprocess.run(['python','/content/l2612-stepH/intervene_H.py'],stdout=open(O/'intervene.log','a'),stderr=subprocess.STDOUT);say(f'intervene rc={i.returncode}')
    b.wait();say(f'b rc={b.returncode}')
(O/'chain.done').write_text('ok\n');say('chain done')
