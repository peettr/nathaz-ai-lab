from pathlib import Path
import subprocess,hashlib,json,sys
R=Path(__file__).resolve().parent; CFG=str(R/'sessions.json');SES='luw-b2u-1017'
def cli(*args):
 p=subprocess.run(['colab','--auth','oauth2','--config',CFG,*args],capture_output=True,text=True,timeout=160)
 print(args[0],p.returncode,(p.stdout+p.stderr)[-1000:],flush=True)
 if p.returncode:raise RuntimeError(args)
root='/content/b2u_case/'
pairs={'offset_samples_a_r10.json':'offset_samples_a_r10.json','case/RESULTS/city_stability.csv':'B2u_trace.csv','result.sha256':'result.sha256','trace.sha256':'trace.sha256','progress.log':'progress.log','case.exit':'case.exit','extract.log':'extract.log','short_gate.json':'short_gate.json','build.log':'build.log'}
for remote,local in pairs.items():cli('download','-s',SES,root+remote,str(R/local))
for file,sha in [('offset_samples_a_r10.json','result.sha256'),('B2u_trace.csv','trace.sha256')]:
 p=R/file;assert p.stat().st_size>100,(file,p.stat().st_size)
 expected=(R/sha).read_text().split()[0];got=hashlib.sha256(p.read_bytes()).hexdigest()
 assert expected==got,(file,expected,got)
 print('VERIFIED',file,p.stat().st_size,got,flush=True)
a=json.loads((R/'offset_samples_a_r10.json').read_text());assert len(a['rows'])==80 and {q['id'] for q in a['rows']}==set(range(1,81))
assert (R/'case.exit').read_text().startswith('0 None')
# Run local comparison and insist on valid output before releasing VM.
p=subprocess.run(['python3',str(R/'compare.py')],capture_output=True,text=True,timeout=120)
print('COMPARE',p.returncode,(p.stdout+p.stderr)[-1600:],flush=True)
if p.returncode:raise RuntimeError('analysis failed; leave Colab running')
cli('stop','-s',SES)
print('STOPPED after retrieval',flush=True)
