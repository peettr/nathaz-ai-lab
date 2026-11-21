import importlib.util
for name in ('numpy','pandas','h5py','fsspec','eccodes','scipy','sklearn','matplotlib','requests'):
 print(name,bool(importlib.util.find_spec(name)))
