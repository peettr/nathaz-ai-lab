import json,time
from pathlib import Path
from vllm import SamplingParams
which='30b' if '--model30b' in __import__('sys').argv else '8b'
rows=[json.loads(s) for s in Path('/content/eval_set_v3.jsonl').read_text().splitlines() if json.loads(s)['group']=='C']
prompts=[tok.apply_chat_template([{'role':'system','content':'You answer a single evaluation question. Do not use external tools. Output only the requested JSON, without explanation.'},{'role':'user','content':x['prompt']}],tokenize=[已隐去],add_generation_prompt=True,enable_thinking=False) for x in rows]
t=time.monotonic();responses=llm.generate(prompts,SamplingParams(temperature=0,max_tokens=[已隐去];out=[{'id':x['id'],'group':'C','response':r.outputs[0].text,'input_tokens':len(tok.encode(p)),'output_tokens':len(r.outputs[0].token_ids)} for x,p,r in zip(rows,prompts,responses)]
Path('/content/'+which+'_c_v3.json').write_text(json.dumps({'rows':out,'elapsed_s':time.monotonic()-t}));print('COMPLETE',which,len(out),round(time.monotonic()-t,2),out[:2],flush=True)
