"""Load official 2.15 Keras checkpoint in isolated Python 3.10 VM env."""
import subprocess, pathlib, urllib.request, zipfile, io, os
p=pathlib.Path('/content/hrrrcast_model.keras');assert p.exists()
def run(args):
 print('RUN',args,flush=True);subprocess.run(args,check=True,timeout=400)
run(['pip','-q','install','uv'])
run(['uv','venv','--python','3.10','/content/hrrr_env'])
run(['uv','pip','install','--python','/content/hrrr_env/bin/python','tensorflow==2.15.0','numpy<2'])
repo=pathlib.Path('/content/HRRRCast-live-master')
if not repo.exists():
 raw=urllib.request.urlopen('https://github.com/NOAA-GSL/HRRRCast-live/archive/refs/heads/master.zip',timeout=60).read()
 zipfile.ZipFile(io.BytesIO(raw)).extractall('/content')
code='import sys;sys.path.insert(0,"/content/HRRRCast-live-master/src");import tensorflow as tf;import resnet;print("TF",tf.__version__,"GPU",tf.config.list_physical_devices("GPU"),flush=True);m=tf.keras.models.load_model("/content/hrrrcast_model.keras",safe_mode=False,compile=False);print("LOADED",m.input_shape,m.output_shape,flush=True)'
run(['/content/hrrr_env/bin/python','-c',code])
