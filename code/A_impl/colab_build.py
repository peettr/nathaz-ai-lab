from pathlib import Path
import tarfile, subprocess, time, shutil
r=Path('/content/luw_wp1_a_v1');r.mkdir(exist_ok=True)
(r/'.colab_owner').write_text('LUW WP1-A research-chat 10-15 16:35 EDT')
with tarfile.open('/content/A_stage_v1.tar.gz') as tf: tf.extractall(r,filter='data')
s=r/'FluidX3D'; d=s/'src/defines.hpp'
t=d.read_text();assert t.count('//#define GROUND_WALL_MODEL')==1
d.write_text(t.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL').replace('//#define GROUND_WALL_FILTER','#define GROUND_WALL_FILTER'))
a=time.monotonic()
with (r/'build.log').open('w') as f: p=subprocess.run(['make','Linux','-j4'],cwd=s,stdout=f,stderr=subprocess.STDOUT,timeout=300)
print('BUILD',p.returncode,'seconds',round(time.monotonic()-a,1),'tail', '\n'.join((r/'build.log').read_text(errors='replace').splitlines()[-25:]),flush=True)
(r/'build_rc.txt').write_text(str(p.returncode))
