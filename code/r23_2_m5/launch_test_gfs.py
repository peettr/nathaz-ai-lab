from pathlib import Path
import subprocess
p=Path('/content/m5')
assert (p/'d1_coefficients.json').exists()
assert (p/'train_pairs.parquet').exists()
assert not (p/'test_gfs.done').exists()
proc=subprocess.Popen(['nohup','bash','/content/m5/test_gfs.sh'],stdin=subprocess.DEVNULL,stdout=(p/'test_gfs.launch').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
print('TEST_GFS_PID',proc.pid)
