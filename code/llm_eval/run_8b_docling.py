from transformers import AutoTokenizer
from vllm import LLM
name='Qwen/Qwen3-8B';tok=AutoTokenizer.from_pretrained(name)
llm=LLM(model=name,max_model_len=8192,gpu_memory_utilization=.88,download_dir='/content/hf_cache',enable_prefix_caching=True,max_num_seqs=16)
exec(open('/content/run_docling.py').read())
