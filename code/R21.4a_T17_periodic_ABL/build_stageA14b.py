from pathlib import Path
import shutil,datetime,json,hashlib,difflib
base=Path(__file__).resolve().parent
old=base/'stageA14_20261119_202355'
r=base/('stageA14_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
r.mkdir(exist_ok=False)
for n in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','machine.py','stub_solver.py','t17_stage.tar.gz','t17_manifest.json','dry_run.py'):
 shutil.copy2(old/n,r/n)
p=r/'worker_full.py';s=p.read_text().replace("'a7':360", "'a7':260").replace("'speed_bounce':70,'speed_t4':70,'speed_t15':70", "'speed_bounce':50,'speed_t4':50,'speed_t15':50");p.write_text(s)
p=r/'controller_full.py';s=p.read_text().replace("(25+360+70*3+90+120)","(25+260+50*3+90+100)");p.write_text(s)
for n in ('worker_full.py','controller_full.py'):
 (r/(n+'.diff')).write_text(''.join(difflib.unified_diff((old/n).read_text().splitlines(True),(r/n).read_text().splitlines(True),fromfile='A14a/'+n,tofile='A14b/'+n)))
(r/'SOURCE_SHA256.json').write_text(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','t17_stage.tar.gz','t17_manifest.json')},indent=2)+'\n')
print(r)
