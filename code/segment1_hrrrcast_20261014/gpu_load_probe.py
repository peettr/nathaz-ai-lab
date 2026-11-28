"""Bounded HRRRCast checkpoint/GPU inference compatibility test; no event score."""
import hashlib, io, json, os, pathlib, subprocess, time, urllib.request, zipfile
p=pathlib.Path('/content/hrrrcast_model.keras')
u='https://media.githubusercontent.com/media/NOAA-GSL/HRRRCast-live/master/net-diffusion/model.keras'
expected='2edef5a5a32cd31f9a6b89ea0b0a54f36d4c528fc20990645debf9446a9315a5'
if not p.exists():
    with urllib.request.urlopen(u, timeout=120) as source, p.open('xb') as dest:
        while data:=source.read(1024*1024): dest.write(data)
h=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert p.stat().st_size==203112115 and h==expected,(p.stat().st_size,h)
print('WEIGHT_VERIFIED',p.stat().st_size,h,flush=True)
repo=pathlib.Path('/content/HRRRCast-live-master')
if not repo.exists():
    raw=urllib.request.urlopen('https://github.com/NOAA-GSL/HRRRCast-live/archive/refs/heads/master.zip',timeout=90).read()
    zipfile.ZipFile(io.BytesIO(raw)).extractall('/content')
subprocess.run(['pip','-q','install','uv'],check=True,timeout=180)
subprocess.run(['uv','venv','--python','3.10','/content/hrrr_env'],check=True,timeout=180)
subprocess.run(['uv','pip','install','--python','/content/hrrr_env/bin/python','tensorflow[and-cuda]==2.15.1','numpy<2'],check=True,timeout=600)
code='''import os,sys,time,json,numpy as np
sys.path.insert(0,"/content/HRRRCast-live-master/src")
import tensorflow as tf
import resnet
print("TF",tf.__version__,"GPU",tf.config.list_physical_devices("GPU"),flush=True)
t=time.monotonic();m=tf.keras.models.load_model("/content/hrrrcast_model.keras",safe_mode=False,compile=False)
print("LOADED",m.input_shape,m.output_shape,time.monotonic()-t,flush=True)
gpus=tf.config.list_physical_devices("GPU")
if not gpus: raise RuntimeError("TensorFlow isolated environment has no GPU")
# This is a synthetic tensor compatibility smoke only, never a meteorological prediction.
shape=tuple(1 if x is None else x for x in m.input_shape)
print("SMOKE_SHAPE",shape,flush=True)
if np.prod(shape)>100000000: raise RuntimeError("synthetic full-grid input too large for bounded smoke")
with tf.device('/GPU:0'):
 x=tf.zeros(shape,dtype=tf.float32)
 t=time.monotonic();y=m(x,training=False)
 print("FORWARD",str(y.shape),round(time.monotonic()-t,2),flush=True)
open('/content/hrrrcast_segment1_probe.json','w').write(json.dumps({'weight_sha256':"2edef5a5a32cd31f9a6b89ea0b0a54f36d4c528fc20990645debf9446a9315a5",'tensorflow':tf.__version__,'gpu':str(gpus),'input_shape':shape,'output_shape':str(y.shape),'synthetic_forward_sec':time.monotonic()-t}))
'''
subprocess.run(['/content/hrrr_env/bin/python','-u','-c',code],check=True,timeout=600)
