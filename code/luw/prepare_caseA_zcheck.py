from pathlib import Path
r=Path(__file__).parent
for name in ('bootstrap_caseA_official.py','launch_caseA_official.py','extract_caseA_official.py'):
    s=(r/name).read_text().replace('luw-aij-caseA-official','luw-aij-caseA-zcheck')
    if name.startswith('extract'):
        s=s.replace("'plus_xy':interp(p['x']+dx,p['y']+dx,p['z'])", "'plus_xy':interp(p['x']+dx,p['y']+dx,p['z']),'plus_xyz':interp(p['x']+dx,p['y']+dx,p['z']+dx)")
        s=s.replace("'samples_caseA_official.json'", "'samples_caseA_zcheck.json'")
    (r/name.replace('official','zcheck')).write_text(s)
print('zcheck scripts ready')
