import pathlib, subprocess
p=pathlib.Path('/content')
print('MARKER', (p/'try9_start.marker').read_text() if (p/'try9_start.marker').exists() else 'ABSENT')
print('PROC',subprocess.run(['pgrep','-af','try9_launch.py'],capture_output=True,text=True).stdout[:500])
print('LOG', (p/'try9_run.log').read_text()[-1200:] if (p/'try9_run.log').exists() else 'ABSENT')
print('OUTPUTS',[(x.name,x.stat().st_size) for x in p.glob('wall_gate0*.csv')])
