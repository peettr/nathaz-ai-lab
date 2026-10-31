import sys
from vllm import LLM
from transformers import AutoTokenizer
name='Qwen/Qwen3-30B-A3B-Instruct-2507-FP8'
tok=AutoTokenizer.from_pretrained(name)
llm=LLM(model=name,max_model_len=8192,gpu_memory_utilization=.88,download_dir='/content/hf_cache',enable_prefix_caching=True,max_num_seqs=16)
sys.argv.append('--model30b')
exec(open('/content/run_c_v3.py').read())
