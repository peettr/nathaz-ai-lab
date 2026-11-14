import json, time, os, sys
from pathlib import Path
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer
which='30b' if '--model30b' in sys.argv else '8b'
models={'8b':'Qwen/Qwen3-8B','30b':'Qwen/Qwen3-30B-A3B-Instruct-2507-FP8'}
name=models[which]; start=time.monotonic()
print('START',which,name,flush=True)
items=[json.loads(s) for s in Path('/content/eval_set.jsonl').read_text().splitlines()]
tok=AutoTokenizer.from_pretrained(name,trust_remote_code=True)
prompts=[]
for x in items:
 messages=[{'role':'system','content':'You answer a single evaluation question. Do not use external tools. Output only the requested JSON, without explanation.'},{'role':'user','content':x['prompt']}]
 try:p=tok.apply_chat_template(messages,tokenize=[已隐去],add_generation_prompt=True,enable_thinking=False)
 except TypeError:p=tok.apply_chat_template(messages,tokenize=[已隐去],add_generation_prompt=True)
 prompts.append(p)
lengths=[len(tok.encode(p)) for p in prompts]
print('TOKEN LENGTHS',max(lengths),sum(lengths),flush=True)
llm=LLM(model=name,trust_remote_code=True,max_model_len=max(8192,max(lengths)+256),gpu_memory_utilization=.88,enable_prefix_caching=True,download_dir='/content/hf_cache',max_num_seqs=16,tensor_parallel_size=1)
out=[]
for k in range(0,len(items),10):
 t=time.monotonic()
 res=llm.generate(prompts[k:k+10],SamplingParams(temperature=0,max_tokens=[已隐去]
 for item,ans,L in zip(items[k:k+10],res,lengths[k:k+10]):
  out.append({'id':item['id'],'group':item['group'],'response':ans.outputs[0].text,'input_tokens':L,'output_tokens':len(ans.outputs[0].token_ids)})
 Path('/content/'+which+'_responses.json').write_text(json.dumps({'model':name,'rows':out,'elapsed_s':time.monotonic()-start,'input_tokens':sum(z['input_tokens'] for z in out),'output_tokens':sum(z['output_tokens'] for z in out)},ensure_ascii=False))
 print('BATCH',k//10+1,'done',len(out),'sec',round(time.monotonic()-t,1),'total_s',round(time.monotonic()-start,1),flush=True)
print('COMPLETE',which,'elapsed_s',round(time.monotonic()-start,1),flush=True)
