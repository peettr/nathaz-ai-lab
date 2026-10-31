import json, subprocess, hashlib, os, pathlib, time
root=pathlib.Path(__file__).parent
inp=root.parent/'questions_set2.jsonl'
assert hashlib.sha256(inp.read_bytes()).hexdigest()=='094a8db049c1bc24b8af5132019f20a73ae3a300c14911804a6c5a0040a648c9'
ctx='[已隐去]'
for row in map(json.loads,inp.read_text().splitlines()):
    for lang,key in [('zh','q'),('en','q_en')]:
        name=f"{row['id']}_{lang}"
        target=root/'raw'/f'{name}.txt'
        if target.exists():
            print('EXISTS SKIP',name,flush=True)
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['rc-kb','--ctx',ctx,'figs',row[key],'-n','5'],capture_output=True,text=True,timeout=240)
        # Save even failures, never automatically repeat a frozen query.
        target.write_text(f'EXIT_CODE={p.returncode}\nQUERY={row[key]}\n'+p.stdout+'\nSTDERR:\n'+p.stderr)
        print(name,p.returncode,len(p.stdout),flush=True)
        if p.returncode: raise SystemExit(f'query failed {name}; no automatic retry')
