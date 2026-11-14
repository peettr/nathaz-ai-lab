"""Diagnose HRRRCast Keras load in pinned TF environment."""
import subprocess,time
s='import sys,time;sys.path.insert(0,"/content/HRRRCast-live-master/src");print("start",flush=True);import tensorflow as tf;print("tf",tf.__version__,flush=True);import resnet;print("custom",flush=True);t=time.monotonic();m=tf.keras.models.load_model("/content/hrrrcast_model.keras",safe_mode=False,compile=False);print("LOADED",m.input_shape,m.output_shape,time.monotonic()-t,flush=True)'
p=subprocess.Popen(['/content/hrrr_env/bin/python','-u','-c',s],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
try:
 for line in p.stdout: print('HRRR',line.rstrip(),flush=True)
finally: print('EXIT',p.wait(),flush=True)
