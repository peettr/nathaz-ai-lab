import os, importlib.util
os.makedirs('/content/m5',exist_ok=True)
print({x:bool(importlib.util.find_spec(x)) for x in ['numpy','pandas','eccodes','pyarrow','requests']})
