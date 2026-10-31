"""L26.14: local, zero-shot text inference on two public safetensors checkpoints."""
import gc
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path('/content/l2614')
ROOT.mkdir(exist_ok=True)
OUT = ROOT / 'out'
OUT.mkdir(exist_ok=True)
MODELS = {'A': 'OpenDCAI/Omni-Edu-9B', 'B': 'Qwen/Qwen3.5-9B'}
SYSTEM = {
    'solve': '你是大学风工程课程助教。请完整解答下面的题目：写出关键推导或理由，给出最终答案并标明单位。',
    'diagnose': '你是大学风工程课程助教。下面是一道题和一位学生的作答。请指出学生错在哪一步、反映了什么误解，并给出正确做法；有数值的给出正确结果。',
    'socratic': '你是大学风工程课程助教，采用苏格拉底式引导。学生在向你求助。不要直接给出最终答案或完整解法；先用一句话指出他可能卡在哪里，再给一个提示或提一个引导问题，帮助他自己走下一步。',
}
MAX_NEW = 8192

def log(*a):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), *a, flush=True)

def install():
    import importlib.metadata
    try:
        v = importlib.metadata.version('transformers')
        if int(v.split('.')[0]) >= 5:
            log('transformers already', v)
            return
    except importlib.metadata.PackageNotFoundError:
        pass
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-input', '-U', 'transformers>=5.2.0', 'accelerate', 'safetensors', 'huggingface_hub'], check=True)

def run():
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ.pop('HF_TOKEN', None)
    os.environ.pop('HUGGING_FACE_HUB_TOKEN', None)
    os.environ.pop('HUGGINGFACEHUB_API_TOKEN', None)
    install()
    import torch
    import transformers
    from huggingface_hub import HfApi
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration
    log('versions', torch.__version__, transformers.__version__, 'cuda', torch.cuda.get_device_name(0))
    items = [json.loads(x) for x in (ROOT / 'items_public.jsonl').read_text().splitlines()]
    assert len(items) == 30 and len({x['id'] for x in items}) == 30
    assert all(set(x) == {'id', 'task_mode', 'question', 'student_answer'} for x in items)
    info = {}
    for label, repo in MODELS.items():
        commit = HfApi(token=[已隐去], token=[已隐去]
        info[label] = {'repo': repo, 'commit': commit, 'template': 'qwen3_5_nothink (enable_thinking=False)', 'transformers': transformers.__version__, 'torch': torch.__version__}
        (OUT / 'provenance.json').write_text(json.dumps(info, ensure_ascii=False, indent=2))
        log('loading', label, repo, commit)
        proc = AutoProcessor.from_pretrained(repo, revision=commit, trust_remote_code=False, token=[已隐去]
        model = Qwen3_5ForConditionalGeneration.from_pretrained(repo, revision=commit, torch_dtype=torch.bfloat16, device_map='auto', use_safetensors=True, trust_remote_code=False, token=[已隐去], low_cpu_mem_usage=True).eval()
        target = OUT / ('answers_' + label + '.jsonl')
        prior = [json.loads(s) for s in target.read_text().splitlines()] if target.exists() else []
        seen = {x['id'] for x in prior}
        for idx, item in enumerate(items, 1):
            if item['id'] in seen:
                continue
            text = item['question'] if item['task_mode'] != 'diagnose' else '题目：' + item['question'] + '\n学生作答：' + item['student_answer']
            messages = [{'role':'system', 'content':[{'type':'text', 'text':SYSTEM[item['task_mode']]}]}, {'role':'user', 'content':[{'type':'text', 'text':text}]}]
            inp = proc.apply_chat_template(messages, add_generation_prompt=True, tokenize=[已隐去], return_dict=True, return_tensors='pt', enable_thinking=False).to(model.device)
            prompt_len = inp['input_ids'].shape[-1]
            start = time.monotonic()
            with torch.inference_mode():
                result = model.generate(**inp, max_new_tokens=[已隐去], do_sample=False)
            tokens = [已隐去] - prompt_len)
            answer = proc.batch_decode(result[:, prompt_len:], skip_special_tokens=[已隐去]
            last_id = int(result[0, -1])
            truncated = tokens >= MAX_NEW and last_id not in set(model.generation_config.eos_token_id if isinstance(model.generation_config.eos_token_id, list) else [model.generation_config.eos_token_id])
            row = {'id':item['id'], 'model':repo, 'answer':answer, 'tokens':tokens, 'truncated':bool(truncated)}
            with target.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
            log(label, idx, item['id'], 'tokens', tokens, 'truncated', truncated, 'sec', round(time.monotonic()-start, 1))
        del model, proc
        gc.collect()
        torch.cuda.empty_cache()
        log('finished model', label)
    for label in MODELS:
        rows = [json.loads(s) for s in (OUT / ('answers_' + label + '.jsonl')).read_text().splitlines()]
        assert len(rows) == 30 and {x['id'] for x in rows} == {x['id'] for x in items}
    (ROOT / 'run.done').write_text('ok\n')
    log('ALL DONE')

if __name__ == '__main__':
    try:
        run()
    except BaseException:
        import traceback
        traceback.print_exc()
        (ROOT / 'run.failed').write_text(traceback.format_exc())
        raise
