#!/usr/bin/env python3
"""L26.14 v2: Colab-only, safetensors-only two-model zero-shot runner."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/content/l26v2')
MODELS = {'A': ('OpenDCAI/Omni-Edu-9B', '4d1222d6224fc4ed874853054bc13db936eb37c5'),
          'B': ('Qwen/Qwen3.5-9B', 'c202236235762e1c871ad0ccb60c8ee5ba337b9a')}
EXPECTED_HASH = 'a25b6f7be74133d53a2bbcbc971a0876661b66ce7e69937479c77aafc09cd0af'
SYS = {
 'solve': '你是大学风工程课程助教。请完整解答下面的题目：写出关键推导或理由，给出最终答案并标明单位。',
 'diagnose': '你是大学风工程课程助教。下面是一道题和一位学生的作答。请指出学生错在哪一步、反映了什么误解，并给出正确做法；有数值的给出正确结果。',
 'socratic': '你是大学风工程课程助教，采用苏格拉底式引导。学生在向你求助。不要直接给出最终答案或完整解法；先用一句话指出他可能卡在哪里，再给一个提示或提一个引导问题，帮助他自己走下一步。'
}

def lines():
    p = ROOT/'items.jsonl'
    assert hashlib.sha256(p.read_bytes()).hexdigest() == EXPECTED_HASH
    data = [json.loads(s) for s in p.read_text().splitlines()]
    assert len(data) == 20 and len({x['id'] for x in data}) == 20
    return data

def prompts(data, tokenizer):
    for x in data:
        for mode in ('solve','diagnose','socratic'):
            user = x['question'] if mode == 'solve' else ('题目：' + x['question'] + '\n学生作答：' + x['student_answer'] if mode == 'diagnose' else '题目：' + x['question'] + '\n学生：' + x['socratic_student_msg'])
            # Explicit allowlist: no reference, diag_reference, rubric or other answer field.
            messages = [{'role':'system','content':SYS[mode]}, {'role':'user','content':user}]
            yield x['id'], mode, tokenizer.apply_chat_template(messages, tokenize=[已隐去], add_generation_prompt=True, enable_thinking=False)

def worker(label):
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    repo, revision = MODELS[label]
    dest = ROOT / ('weights_'+label)
    print('download',label,repo,revision,flush=True)
    path = snapshot_download(repo_id=repo, revision=revision, local_dir=str(dest),
      allow_patterns=['*.safetensors','*.json','*.jinja','*.model','*.txt','*.tiktoken','*.vocab','merges.txt'],
      ignore_patterns=['*.py','*.bin','*.pt','*.pth','*.ckpt','*.pkl','*.pickle','*.gguf'])
    weights = list(dest.glob('*.safetensors'))
    assert weights and not list(dest.glob('*.bin'))
    print('safetensors',label,len(weights),sum(p.stat().st_size for p in weights),flush=True)
    tok = AutoTokenizer.from_pretrained(path, trust_remote_code=False)
    tasks = list(prompts(lines(),tok))
    assert len(tasks) == 60
    out = ROOT / ('answers_'+label+'.jsonl')
    done = {}
    if out.exists():
        for row in map(json.loads,out.read_text().splitlines()):
            key=(row['id'],row['task_mode'])
            assert key not in done and row['model']==repo
            done[key]=row
    print('load engine',label,'pending',len(tasks)-len(done),flush=True)
    engine=LLM(model=path, tokenizer=[已隐去], trust_remote_code=False, load_format='safetensors',
       dtype='bfloat16', max_model_len=10000, max_num_seqs=1,
       gpu_memory_utilization=0.86, language_model_only=True,
       enforce_eager=True)
    params=SamplingParams(temperature=0, max_tokens=[已隐去]
    with out.open('a') as f:
        for k,(ident,mode,prompt) in enumerate(tasks):
            if (ident,mode) in done: continue
            result=engine.generate([prompt],params,use_tqdm=False)[0].outputs[0]
            row={'id':ident,'task_mode':mode,'model':repo,'answer':result.text,
                 'tokens':len(result.token_ids),'truncated':result.finish_reason=='length'}
            f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
            print(label,k+1,'/60',ident,mode,'tokens',row['tokens'],'finish',result.finish_reason,flush=True)
    assert len(out.read_text().splitlines()) == 60
    del engine;gc.collect()

def main():
    ROOT.mkdir(exist_ok=True)
    for label in ('A','B'):
        print('BEGIN',label,time.strftime('%Y-%m-%d %H:%M:%S'),flush=True)
        subprocess.run([sys.executable,__file__,'--worker',label],check=True)
        print('END',label,time.strftime('%Y-%m-%d %H:%M:%S'),flush=True)
    (ROOT/'run.done').write_text('ok\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker',choices=['A','B']);a=ap.parse_args()
    if a.worker:worker(a.worker)
    else:main()
