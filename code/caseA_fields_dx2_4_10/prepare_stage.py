"""Prepare frozen 4/10 m input decks from the registered 2 m r9 deck; no solver run."""
from pathlib import Path
import hashlib, json, shutil
base = Path(__file__).resolve().parents[1]
out = base/'caseA_fields_dx2_4_10'/'stage'
old = base/'caseA_r9_2m_tacc_v2'/'stage'
assert not out.exists(), f'fresh stage required: {out}'
assert hashlib.sha256((old/'source_dd438c1.tar.gz').read_bytes()).hexdigest() == '88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
out.mkdir()
shutil.copy2(old/'source_dd438c1.tar.gz', out)
text = (old/'caseA/conf.luwpf').read_text()
for dx, steps, avg, stride in [(4,16000,11000,20),(10,6400,4400,8)]:
    case = out/f'caseA_dx{dx}'
    (case/'proj_temp').mkdir(parents=True)
    (case/'wind_bc').mkdir()
    shutil.copy2(old/'caseA/proj_temp/CaseA_PF.stl',case/'proj_temp/CaseA_PF.stl')
    shutil.copy2(old/'caseA/wind_bc/profile.dat',case/'wind_bc/profile.dat')
    changes = {'cell_size = 2.0': f'cell_size = {dx:.1f}', 'run_nstep = 32000':f'run_nstep = {steps}', 'purge_avg = 22000':f'purge_avg = {avg}', 'purge_avg_stride = 40':f'purge_avg_stride = {stride}'}
    new = text
    for before, after in changes.items():
        assert new.count(before)==1, (before,new.count(before))
        new=new.replace(before,after)
    (case/'conf.luwpf').write_text(new)
shutil.copy2(base/'caseA_r9_2m_tacc_v2'/'stage'/'run_caseA.sh',out/'reference_run_caseA.sh')
print(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()},indent=2))
