from pathlib import Path
import shutil
r=Path(__file__).parent
src=r.parent/'directional'
for f in ('c2a_driver.py','c2a_worker.sh','c2a_solve.qsub','harvest.py','rss_sampler.py'):
    shutil.copyfile(src/f,r/f)
p=r/'c2a_driver.py';s=p.read_text();s=s.replace('"""C2a diagnostic cells only; original five-cell gate remains unchanged."""','"""Final SA coarse uniform inlet / slip top directional check."""')
start=s.index('# Third-run cell-wise FD is INVALID:')
end=s.index("status('DIRECTIONS_START')",start)
endpoint_start=s.index('def cold_endpoint(label,target):',start)
endpoint_end=s.index('\nrows=[]',endpoint_start)
endpoint=s[endpoint_start:endpoint_end]
s=s[:start]+'''# Pre-registered directions only; no per-cell diagnostic in this final comparison.\nimport hashlib\nfrom numpy.random import default_rng\nif comm.rank==0:\n (case/'c2a_gradient.json').write_text(json.dumps({'abs_max':float(np.max(np.abs(grad)))},indent=2)+'\\n')\nstatus('GRADIENT_SAVED')\n\n'''+endpoint+'\n'+s[end:]
s=s.replace('for h in (1e-3,1e-2):\n  ends=[]\n  for sign in (1,-1):\n   target=1+sign*h*v', 'for h in (1e-3,):\n  ends=[]\n  for sign in (1,-1):\n   target=1+sign*h*v')
p.write_text(s)
# SA patch itself is otherwise unchanged; override only top in separate script after patching.
(r/'set_uniform_slip.py').write_text('''#!/usr/bin/env python3\n"""Only inlet and top boundary variants on the copied SA case."""\nimport re,sys\nfrom pathlib import Path\nc=Path(sys.argv[1]); nu_text=(c/'constant/transportProperties').read_text()\nm=re.search(r'\\bnu\\s*\\[[^]]+\\]\\s*([\\deE.+-]+)\\s*;',nu_text); assert m, 'nu missing'\nnu=float(m[1]); val=3*nu; assert 0<nu<1e-3\nfor field in ('U','nuTilda','p'):\n p=c/'0'/field; text=p.read_text()\n if field=='U':\n  inlet='inlet { type fixedValue; value uniform (10 0 0); }'; top='top { type slip; }'\n elif field=='nuTilda':\n  inlet=f'inlet {{ type fixedValue; value uniform {val:.12g}; }}'; top='top { type zeroGradient; }'\n else:\n  inlet=None;top='top { type zeroGradient; }'\n if inlet:\n  text,k=re.subn(r'\\binlet\\s*\\{[^{}]*\\}',inlet,text,count=1,flags=re.S);assert k==1,(field,'inlet')\n text,k=re.subn(r'\\btop\\s*\\{[^{}]*\\}',top,text,count=1,flags=re.S);assert k==1,(field,'top')\n p.write_text(text)\nprint('UNIFORM_SLIP_OK nu=',nu,'nuTilda=',val, 'top_patch=patch')\n''')
p=r/'c2a_worker.sh';s=p.read_text();s=s.replace('run python "$R/build_sa_inlet.py" "$C" > "$R/logs/inlet.log" 2>&1 || exit 35','run python "$R/set_uniform_slip.py" "$C" > "$R/logs/inlet.log" 2>&1 || exit 35')
s=s.replace('stage C2A_INPUT_READY \'mesh=168206, boundaries=ok\'','stage C2A_INPUT_READY \'mesh=168206, uniform_inlet_slip_top_boundaries=ok\'')
s=s.replace(' C2a_dir ', ' C2a_final ')
p.write_text(s)
p=r/'c2a_solve.qsub';s=p.read_text();s=s.replace('L26_21_C2a_dir','L26_21_C2a_final').replace('h_rt=01:30:00','h_rt=01:00:00').replace('3690s','3560s').replace('3450 - ELAPSED','3320 - ELAPSED').replace('L26_21_DAFOAM_20261115_C2a_directional','L26_21_DAFOAM_20261115_C2a_final_uniform').replace('c2a_directional.exitcode','c2a_final.exitcode').replace('"$R/build_sa_inlet.py"','"$R/set_uniform_slip.py"')
p.write_text(s)
