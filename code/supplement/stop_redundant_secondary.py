from pathlib import Path
import os,signal,time,subprocess
p=Path('/content/m6');pid=9921
cmd=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\x00',b' ').decode()
assert cmd.strip()=='python3 -u m6_score.py test',cmd
assert not (p/'score_rebuilt.done').exists()
assert (p/'test_predictions_delay4.parquet').exists()
print('CANCEL_REPEATED_SECONDARY',pid,'core delay4 already written; archived secondary retained locally')
os.kill(pid,signal.SIGTERM)
for i in range(30):
    if not Path(f'/proc/{pid}').exists():break
    time.sleep(.2)
print('live',Path(f'/proc/{pid}').exists())
