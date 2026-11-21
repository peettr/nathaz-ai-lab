import pathlib,subprocess
r=pathlib.Path('/content/r234c_gc37_E2E3')
for name in ['numeric_gate_worker_v2.log','numeric_gate_worker.exit.json','INPUT_NUMERIC_GATE_E2E3_V2.jsonl']:
 p=r/name
 print(name,p.exists(),p.stat().st_size if p.exists() else None,p.read_text()[-1200:] if p.exists() and p.stat().st_size<500000 else '')
print(subprocess.run(['pgrep','-af','launch_numeric_gate_e2e3_25cu_v2'],capture_output=True,text=True).stdout)
