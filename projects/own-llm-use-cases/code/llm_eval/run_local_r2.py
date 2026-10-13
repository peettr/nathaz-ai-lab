import json,os,time
from pathlib import Path
from vllm import LLM,SamplingParams
from transformers import AutoTokenizer
model_id=os.environ.get('R2_MODEL','30b')
models={'30b':'Qwen/Qwen3-30B-A3B-Instruct-2507-FP8','32b':'Qwen/Qwen3-32B-AWQ'}
name=models[model_id];start=time.monotonic();print('START',model_id,name,flush=True)
items=[json.loads(s) for s in Path('/content/gemini_questions_r2.jsonl').read_text().splitlines()]
system=Path('/content/system_r2.txt').read_text().strip();tok=AutoTokenizer.from_pretrained(name,trust_remote_code=True)
ps=[];lens=[]
for item in items:
 m=[{'role':'system','content':system},{'role':'user','content':item['prompt']}]
 try:p=tok.apply_chat_template(m,tokenize=[已隐去],add_generation_prompt=True,enable_thinking=False)
 except TypeError:p=tok.apply_chat_template(m,tokenize=[已隐去],add_generation_prompt=True)
 ps.append(p);lens.append(len(tok.encode(p)))
print('PROMPTS',len(ps),'max',max(lens),'sum',sum(lens),flush=True)
llm=LLM(model=name,trust_remote_code=True,max_model_len=max(8192,max(lens)+256),gpu_memory_utilization=.85,enable_prefix_caching=True,download_dir='/content/hf_cache',max_num_seqs=16,tensor_parallel_size=1)
rows=[]
for k in range(0,len(items),10):
 t=time.monotonic();outs=llm.generate(ps[k:k+10],SamplingParams(temperature=0,max_tokens=[已隐去]
 for item,ans,L in zip(items[k:k+10],outs,lens[k:k+10]):
  rows.append({'id':item['id'],'response':ans.outputs[0].text,'input_tokens':L,'output_tokens':len(ans.outputs[0].token_ids)})
 Path('/content/'+model_id+'_answers_r2.json').write_text(json.dumps({'model':name,'rows':rows,'elapsed_s':time.monotonic()-start,'input_tokens':sum(z['input_tokens'] for z in rows),'output_tokens':sum(z['output_tokens'] for z in rows)}))
 print('BATCH',k//10+1,'done',len(rows),'sec',round(time.monotonic()-t,1),'total',round(time.monotonic()-start,1),flush=True)
print('COMPLETE',model_id,len(rows),'elapsed',round(time.monotonic()-start,1),flush=True)
