#!/usr/bin/env python3.10
"""Resume monitoring an already running T5 worker; never launch a solver or VM."""
import json,time,traceback,sys
import controller as c

allocation=next(json.loads(line) for line in c.EVENT.read_text().splitlines() if json.loads(line).get('event')=='allocated')
assert allocation['endpoint']=='gpu-g4-s-use5a2-24dpexgk64zhi'
c.ENDPOINT=allocation['endpoint'];c.created=allocation['created'];c.deadline=allocation['deadline'];c.rate=allocation['assumed_rate'];c.GPU=allocation['gpu']
c.verified.update({'E_s101_on','E_s101_off'})

def run():
    assert c.global_presence(),'owned endpoint disappeared; reconcile without relaunch'
    # Recheck local files from the previous host acknowledgments, never overwrite them.
    for label in sorted(c.verified):
        for ext in ('thin.npz','points80.json'):
            p=c.O/f'{label}_{ext}'
            assert p.is_file() and p.stat().st_size>0
            assert c.sha(p)==(c.O/f'{label}_{ext}.sha256').read_text().strip()
    absent_count=0
    while True:
        if time.time()>=c.deadline-240:
            c.stop('deadline');return 2
        state,absent=c.monitor_once(c.probe_once,c.global_presence,time.sleep)
        if state is None:
            absent_count=absent_count+1 if absent else 0
            if absent_count>=3:c.stop('endpoint_absent_3');return 2
            continue
        absent_count=0
        c.log('resume_probe',ready=list(state['ready']),ack=state['ack'],done=state['done'],failed=state['failed'],tail=state['log'][-300:])
        for label in c.LABELS:
            keys=[f'{label}_{ext}.sha256' for ext in ('thin.npz','points80.json')]
            if all(k in state['ready'] for k in keys) and label not in c.verified:
                try:c.verify_case(label,state)
                except (Exception,) as e:c.log('resume_transfer_error',label=label,error=str(e)[-450:])
        if state['done'] or state['failed']:
            available_verified=all(not any(k.startswith(label+'_') for k in state['ready']) or label in c.verified for label in c.LABELS)
            if available_verified and (state['failed'] or len(c.verified)==len(c.LABELS)):
                complete=state['done'] and not state['failed'] and len(c.verified)==len(c.LABELS)
                c.stop('terminal_verified');return 0 if complete else 2
        time.sleep(30)

if __name__=='__main__':
    try:sys.exit(run())
    except BaseException as e:
        c.log('resume_error',error=str(e),traceback=traceback.format_exc()[-1500:])
        sys.exit(3)
