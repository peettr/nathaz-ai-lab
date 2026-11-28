from pathlib import Path
import subprocess, os
root=Path('/content/r234c_gc37x_B1')
root.mkdir(parents=True,exist_ok=True)
Path('/root/.config/rclone').mkdir(parents=True,exist_ok=True)
assert Path('/content/colab_worker_gc37x_B1_four_v1.py').is_file()
assert not (root/'worker_gc37x_B1_four_v1.done').exists()
assert not (root/'worker_gc37x_B1_four_v1.failed').exists()
assert not (root/'launch.pid').exists()
with (root/'launcher_stdout.log').open('x') as out:
    p=subprocess.Popen(['python','-u','/content/colab_worker_gc37x_B1_four_v1.py'],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
(root/'launch.pid').write_text(str(p.pid))
print('LAUNCHED',p.pid)
