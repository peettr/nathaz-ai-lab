"""Quick check on benchmark v3 speed run status."""
import os, json
from pathlib import Path

os.environ['LIGHTNING_USER_ID'] = 'fd1e3b1f-23d6-4b4a-916e-e8983f8259b2'
os.environ['LIGHTNING_API_KEY'] = '4c73de3a-230b-4daf-8650-688186de6113'
from lightning_sdk import Studio

STATE_FILE = Path(r'C:\graph-deeponet-wind\results\lightning_run_state_v3.json')
state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
PID = state['remote_pid']
REMOTE_BASE = state['remote_base']

s = Studio(name='ai-scientist', teamspace='performance-benchmark-project', user='[用户]')
print(f'Studio: {s.status}')

cmd = f"""bash -lc '
echo "=== PROCESS ==="
ps -p {PID} -o pid,ppid,stat,etime,cmd 2>/dev/null || echo "Process {PID} not found"
echo "=== GPU ==="
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "No GPU"
echo "=== LOG TAIL ==="
tail -n 15 {REMOTE_BASE}/logs/benchmark_v3_speed.log 2>/dev/null || echo "No log yet"
echo "=== RESULT ==="
ls -la {REMOTE_BASE}/results/benchmark_v3_speed.json 2>/dev/null || echo "No result yet"
'"""
print(s.run(cmd))
