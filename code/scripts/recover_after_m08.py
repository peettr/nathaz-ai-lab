"""Recover m08 after host controller disappeared; never replay an active member."""
import datetime
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import continue_points_only as c
import orchestrate_new as old

R = old.R
S = old.S
SESSION = 'wx-cnew-m08-1015'
REMOTE = '/content/ace_formal/members/m08'
OUT = R / 'results/m08'
START = datetime.datetime.fromisoformat('2026-10-16T08:01:05.585983-04:00')
PREVIOUS = [1.716930218936662, 1.646024178230857, 1.579694938888889,
            1.6824829958333334, 1.5829901066666667, 1.5413362052777777,
            1.5736971819444445]

def main():
    assert not Path('/proc/3318378').exists(), 'original controller alive'
    assert OUT.is_dir() and not any(OUT.iterdir()), 'm08 result not empty'
    assert all((R / 'results' / f'm{k:02d}' / fn).is_file()
               for k in range(1, 8)
               for fn in ('exit.json', 'summary.json', 'pressure_minima.json'))
    old.rec('RECOVER_M08_CONTROLLER_GONE', session=SESSION,
            reason='host PID gone without terminal event; verified remote session and keepalive alive')
    old.watch(SESSION, REMOTE + '/complete.done', REMOTE + '.launcher.log', 7)
    response = old.query(SESSION, f"import json;print('WXEXIT '+json.dumps(json.load(open('{REMOTE}/exit.json'))))\n")
    assert json.loads(response.split('WXEXIT ', 1)[1].splitlines()[0])['returncode'] == 0
    for fn in ('summary.json', 'exit.json', 'pressure_minima.json', 'config.yaml'):
        old.download(SESSION, REMOTE + '/' + fn, OUT / fn)
    pressure = json.loads((OUT / 'pressure_minima.json').read_text())
    assert len(pressure['rows']) == 30
    summary = json.loads((OUT / 'summary.json').read_text())
    assert summary['member'] == 8 and len(summary['years']) == 30
    old.stop(SESSION)
    hours = (datetime.datetime.now().astimezone() - START).total_seconds() / 3600
    c.prior[:] = PREVIOUS + [hours]
    old.rec('MEMBER_COMPLETE', member=8, session=SESSION,
            session_hours=hours, estimated_cu=hours * old.RATE,
            mode='points_pressure_only_recovered')
    for k in (9, 10):
        c.member(k)
    old.rec('ALL_COMPLETE', member_count=10,
            estimated_cu=2 + sum(c.prior) * old.RATE + 3)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        old.rec('HALTED_LEAVE_SESSION_RUNNING', recovery='after_m08', error=repr(exc))
        raise
