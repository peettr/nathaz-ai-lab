import json,time
from pathlib import Path
from vllm import SamplingParams
items=[json.loads(s) for s in Path('/content/eval_set_v2.jsonl').read_text().splitlines() if json.loads(s)['id'] in ('D13','D14','D15')]
prompts=[tok.apply_chat_template([{'role':'system','content':'You answer a single evaluation question. Do not use external tools. Output only the requested JSON, without explanation.'},{'role':'user','content':x['prompt']}],tokenize=[已隐去],add_generation_prompt=True,enable_thinking=False) for x in items]
t=time.monotonic();res=llm.generate(prompts,SamplingParams(temperature=0,max_tokens=[已隐去];rows=[{'id':x['id'],'group':'D','response':r.outputs[0].text,'input_tokens':len(tok.encode(p)),'output_tokens':len(r.outputs[0].token_ids)} for x,p,r in zip(items,prompts,res)]
Path('/content/30b_revised.json').write_text(json.dumps({'rows':rows,'elapsed_s':time.monotonic()-t},ensure_ascii=False))
print('REVISED',rows,'elapsed',time.monotonic()-t,flush=True)
