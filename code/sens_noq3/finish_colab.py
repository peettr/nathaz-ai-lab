import subprocess,sys,pathlib,json,datetime
p=pathlib.Path('/content/sens2');r=pathlib.Path('/content/sens_retry');d=pathlib.Path('/content/sens4')
assert json.loads((r/'qc.done').read_text())['errors']==0
assert json.loads((d/'decision.json').read_text())['n']==29
for name in ('gev_sens_colab_final.py','derive_colab.py'):
 z=subprocess.run([sys.executable,str(p/name)],cwd='/content',capture_output=True,text=True)
 print(name,z.returncode,z.stdout[-2000:],z.stderr[-2000:]);assert z.returncode==0
(r/'analysis.done.json').write_text(json.dumps({'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'n_gev':sum(1 for _ in (d/'gev_with_baseline.csv').open())-1,'n_x10':sum(1 for _ in (d/'x10_changes.csv').open())-1}))
