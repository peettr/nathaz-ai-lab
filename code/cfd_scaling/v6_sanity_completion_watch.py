"""Notify when the ongoing Colab sanity segment writes its small final summary."""
import glob
import json
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = './22_Lab/06_Logs/cfd_scaling'
SESSION = 'ideas-urbantales-v6-1014'
REMOTE = '/content/v6_work/sanity/segment_summary.json'

def stamp():
    return datetime.now(ZoneInfo('America/New_York')).strftime('%m-%d %H:%M')

for _ in range(180):
    matches = glob.glob(ROOT + '/v6_sanity_summary_newrule_*.json')
    for name in sorted(matches, reverse=True):
        try:
            data = json.load(open(name))
            if data.get('segment') == 'sanity':
                print(f'{stamp()} SANITY_SUMMARY {name} holdout={data.get("holdout_median_r2")}', flush=True)
                raise SystemExit(0)
        except (OSError, ValueError):
            pass
    probe = subprocess.run(['colab', '--auth', 'oauth2', 'ls', '-s', SESSION,
                            '/content/v6_work/sanity'], capture_output=True, text=True, timeout=45)
    if probe.returncode == 0 and 'segment_summary.json' in probe.stdout:
        print(f'{stamp()} SANITY_REMOTE_SUMMARY_READY; keepalive may still be pulling', flush=True)
        raise SystemExit(0)
    if probe.returncode == 0 and 'launcher.log' not in probe.stdout:
        print(f'{stamp()} SANITY_SESSION_OR_OUTPUT_MISSING', flush=True)
        raise SystemExit(2)
    time.sleep(90)
print(f'{stamp()} SANITY_WATCH_TIMEOUT', flush=True)
raise SystemExit(3)
