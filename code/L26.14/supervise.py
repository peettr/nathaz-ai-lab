"""Bound owned Colab session and release after durable result pull."""
import datetime
import json
import pathlib
import subprocess
import time

P = pathlib.Path('./26_Quick_Trials/06_Logs/L26.14')
STATE = pathlib.Path('./platform/colab-keepalive/l2614-omni-qwen-quick.json')
CLI = ['colab', '--auth', 'oauth2', '--config', str(P/'colab_state.json')]
NAME = 'l2614-omni-qwen-quick'
START = time.time()
LIMIT_SEC = 95 * 60

def record(s):
    with (P/'supervisor.log').open('a') as f:
        f.write(datetime.datetime.now().astimezone().isoformat() + ' ' + s + '\n')
    print(s, flush=True)

def stop():
    for attempt in range(3):
        p = subprocess.run(CLI + ['stop', '-s', NAME], capture_output=True, text=True, timeout=70)
        record('stop attempt=' + str(attempt) + ' rc=' + str(p.returncode) + ' output=' + (p.stdout+p.stderr)[-700:])
        if p.returncode == 0:
            break
        time.sleep(20)
    p = subprocess.run(CLI + ['sessions'], capture_output=True, text=True, timeout=70)
    record('private sessions rc=' + str(p.returncode) + ' output=' + (p.stdout+p.stderr)[-900:])

record('started max duration sec=' + str(LIMIT_SEC))
while True:
    try:
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        if state.get('state') == 'done' and state.get('final_pull_state') == 'ok':
            record('all final pulls verified; stop')
            stop()
            break
        elapsed = time.time()-START
        if elapsed >= LIMIT_SEC:
            record('budget timer reached; trigger final read-only pull if possible')
            subprocess.run(['./bin/colab-keepalive', '--config', str(P/'colab_state.json'), '-s', NAME, '--log', '/content/l2614/run.log', '--pull', '/content/l2614/out/answers_A.jsonl:'+str(P/'budget_A.jsonl'), '--pull', '/content/l2614/out/answers_B.jsonl:'+str(P/'budget_B.jsonl'), '--keep', '100', '--once'], capture_output=True, text=True, timeout=130)
            stop()
            break
        if state.get('state') in ('session_gone','final_pull_failed','job_ended_no_marker','log_stale','max_hours'):
            record('terminal watcher state=' + str(state.get('state')) + '; stop')
            stop()
            break
    except Exception as e:
        record('monitor exception ' + repr(e))
    time.sleep(60)
