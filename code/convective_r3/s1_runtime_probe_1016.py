import torch,sys,importlib.util
print('PY',sys.version,'TORCH',torch.__version__,'CUDA',torch.version.cuda,'GPU',torch.cuda.get_device_name())
for k in ['natten','physicsnemo','earth2studio','huggingface_hub']:
 print(k,importlib.util.find_spec(k))
