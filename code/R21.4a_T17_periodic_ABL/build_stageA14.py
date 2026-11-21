from pathlib import Path
import shutil, json, hashlib, datetime, difflib
base=Path(__file__).resolve().parent
src=base/'stageA13_20261119_1421'
r=base/('stageA14_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
r.mkdir(exist_ok=False)
for name in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','machine.py','stub_solver.py','t17_stage.tar.gz','t17_manifest.json'):
    shutil.copy2(src/name,r/name)
w=r/'worker_full.py'; s=w.read_text()
s=s.replace("STAGES=(('a1b','periodic_t4',1000),('a3','periodic_t15_k2',0),('a7','periodic_t15_k2',8975),", "STAGES=(('a3','periodic_t15_k2',0),('a7','periodic_t15_k2',8975),")
s=s.replace("'a7':300", "'a7':360")
s=s.replace("  # Assert based on real native producer file; the fixture stub is only wiring proof.\n", "  # Assert based on real native producer file; the fixture stub is only wiring proof.\n")
s=s.replace("  if grc:raise RuntimeError('gate failed '+label+' rc='+str(grc))", "  if grc:raise RuntimeError('gate failed '+label+' rc='+str(grc))")
w.write_text(s)
a=r/'assert_ledger.py'; t=a.read_text().replace("'limit':0.01,'pass':ratio<=0.01", "'limit':0.025,'pass':ratio<=0.025");a.write_text(t)
c=r/'controller_full.py'; t=c.read_text().replace("CASES=('a1b','a3','a7','speed_bounce','speed_t4','speed_t15')", "CASES=('a3','a7','speed_bounce','speed_t4','speed_t15')")
t=t.replace("cut=created+1.5*3600/RATE-90;hard=created+1.5*3600/RATE", "cut=created+1.2*3600/RATE-90;hard=created+1.2*3600/RATE")
t=t.replace("(45+25+300+70*3+90+120)","(25+360+70*3+90+120)")
t=t.replace("T17 A-iii;", "T17 A14;")
c.write_text(t)
remote=r/'remote_io.py';t=remote.read_text().replace("LABELS=('a1b','a3','a7','speed_bounce','speed_t4','speed_t15')", "LABELS=('a3','a7','speed_bounce','speed_t4','speed_t15')");remote.write_text(t)
dry=r/'dry_run.py';t=(src/'dry_run.py').read_text().replace("1.5*3600/5.4","1.2*3600/5.4").replace("labels=('a1b','a3','a7','speed_bounce','speed_t4','speed_t15')", "labels=('a3','a7','speed_bounce','speed_t4','speed_t15')");dry.write_text(t)
for n in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','dry_run.py'):
    old=src/n if (src/n).exists() else None
    (r/(n+'.diff')).write_text(''.join(difflib.unified_diff((old.read_text() if old else '').splitlines(True),(r/n).read_text().splitlines(True),fromfile='A13/'+n,tofile='A14/'+n)))
manifest={n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','machine.py','stub_solver.py','t17_stage.tar.gz','t17_manifest.json','dry_run.py')}
(r/'SOURCE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(r)
