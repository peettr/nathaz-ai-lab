from pathlib import Path
import subprocess
r = Path('/content/r234c_gc37x_B1')
r.mkdir(parents=True, exist_ok=True)
assert Path('/content/colab_worker_gc37x_B1_four_DX1_v2.py').is_file()
assert Path('/content/check_gc37x_inputs_v2.py').is_file()
assert not (r/'worker_gc37x_B1_four_DX1_v2.done').exists()
assert not (r/'worker_gc37x_B1_four_DX1_v2.failed').exists()
assert not (r/'launch_DX1_v2.pid').exists()
with (r/'launcher_DX1_v2_stdout.log').open('x') as out:
    p = subprocess.Popen(['python', '-u', '/content/colab_worker_gc37x_B1_four_DX1_v2.py'],
                         stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                         start_new_session=True)
(r/'launch_DX1_v2.pid').write_text(str(p.pid))
print('LAUNCHED', p.pid)
