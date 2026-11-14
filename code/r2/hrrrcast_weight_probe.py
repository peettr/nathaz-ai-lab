"""Verify public HRRRCast weight on Colab; no event forecast."""
import hashlib, os, time, urllib.request
from pathlib import Path
p=Path('/content/hrrrcast_model.keras')
u='https://media.githubusercontent.com/media/NOAA-GSL/HRRRCast-live/master/net-diffusion/model.keras'
expected='2edef5a5a32cd31f9a6b89ea0b0a54f36d4c528fc20990645debf9446a9315a5'
t=time.monotonic()
if not p.exists():
    with urllib.request.urlopen(u, timeout=120) as source, p.open('wb') as dest:
        while True:
            data=source.read(1024*1024)
            if not data: break
            dest.write(data)
            if dest.tell()%(32*1024*1024)<1024*1024:print('DOWNLOADED',dest.tell(),flush=True)
h=hashlib.sha256()
with p.open('rb') as f:
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
print('WEIGHT',p.stat().st_size,h.hexdigest(),'expected',expected,'seconds',round(time.monotonic()-t,1),flush=True)
assert p.stat().st_size==203112115 and h.hexdigest()==expected
import tensorflow as tf
print('TF',tf.__version__,'GPU',tf.config.list_physical_devices('GPU'),flush=True)
t=time.monotonic()
m=tf.keras.models.load_model(str(p),safe_mode=False,compile=False)
print('MODEL_LOADED',m.input_shape,m.output_shape,'seconds',round(time.monotonic()-t,1),flush=True)
