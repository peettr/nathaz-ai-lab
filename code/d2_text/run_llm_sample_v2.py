"""Second bounded 10-example vLLM trial; preserve the truncated v1 output."""
import argparse, json, pathlib, random, time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--model',default='Qwen/Qwen2.5-7B-Instruct')
    args=ap.parse_args()
    assert not args.output.exists(), 'never overwrite existing results'
    rows=json.loads(args.input.read_text()); assert len(rows)==10
    import torch
    from vllm import LLM, SamplingParams
    random.seed(31026); torch.manual_seed(31026)
    model=LLM(model=args.model,trust_remote_code=False,dtype='float16',max_model_len=2048,
              gpu_memory_utilization=0.85,seed=31026,enforce_eager=True)
    tokenizer=[已隐去]
    prompts=[tokenizer.apply_chat_template([{'role':'user','content':r['prompt']}],tokenize=[已隐去],add_generation_prompt=True) for r in rows]
    t0=time.monotonic()
    outputs=model.generate(prompts,SamplingParams(temperature=0,top_p=1,max_tokens=[已隐去],seed=31026))
    elapsed=time.monotonic()-t0
    for row,item in zip(rows,outputs):
        row['llm']=item.outputs[0].text.strip()
        row['llm_word_count']=len(row['llm'].split())
        row['finish_reason']=item.outputs[0].finish_reason
        row.pop('prompt')
    args.output.write_text(json.dumps({'model':args.model,'gpu':torch.cuda.get_device_name(0),
        'temperature':0,'seed':31026,'sample_count':10,'max_tokens':400,
        'inference_elapsed_sec':elapsed,'samples':rows},ensure_ascii=False,indent=2))
    print('LLM_DONE',elapsed,[(r['llm_word_count'],r['finish_reason']) for r in rows],flush=True)
if __name__=='__main__': main()
