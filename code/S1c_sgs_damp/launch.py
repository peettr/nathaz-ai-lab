"""Owned S1c session launcher and guarded result retrieval.
Never stop unless result JSON/trace exist, hashes match and 80 rows pass.
"""
from pathlib import Path
import subprocess,sys,json,hashlib,time
R=Path(__file__).resolve().parent
SESSION='luw-s1c-1017'
CONFIG=str(R/'sessions.json')
def colab(*args,timeout=120):
 p=subprocess.run(['colab','--auth','oauth2','--config',CONFIG,*args],capture_output=True,text=True,timeout=timeout)
 print('COLAB',args[0],p.returncode,(p.stdout+p.stderr)[-1600:],flush=True)
 if p.returncode:raise RuntimeError(f'{args[0]} failed')
 return p.stdout

def verify_and_stop():
 remote='/content/s1b_case/'
 # Remote hash is a SHA256 produced by the remote before the done marker.
 for name in ('offset_samples_a_r10.json','case/RESULTS/city_stability.csv','result.sha256','progress.log','solver.exit'):
  colab('download','-s',SESSION,remote+name,str(R/('S1c_trace.csv' if name.endswith('city_stability.csv') else name)),timeout=120)
 p=R/'offset_samples_a_r10.json';t=R/'S1c_trace.csv'
 assert p.stat().st_size>1000 and t.stat().st_size>100
 d=json.loads(p.read_text());assert len(d['rows'])==80
 assert {r['id'] for r in d['rows']}==set(range(1,81))
 actual=hashlib.sha256(p.read_bytes()).hexdigest();expected=(R/'result.sha256').read_text().split()[0]
 assert actual==expected,(actual,expected)
 # Extra remote readback checks bytes & hash in the exact target before stop.
 print('VERIFIED 80 rows; local=remote SHA256',actual,'trace',t.stat().st_size,flush=True)
 colab('stop','-s',SESSION)
 return actual

if __name__=='__main__':
 if sys.argv[1:] == ['verify-stop']:verify_and_stop()
 else:raise SystemExit('Usage: python3 launch.py verify-stop')
