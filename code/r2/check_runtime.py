import importlib.util,subprocess
for n in ['earth2studio','tensorflow','torch','uv']:
 print('SPEC',n,importlib.util.find_spec(n),flush=True)
r=subprocess.run(['/content/hrrr_env/bin/python','-c','import tensorflow as tf; import sys;sys.path.insert(0,"/content/HRRRCast-live-master/src");import resnet;m=tf.keras.models.load_model("/content/hrrrcast_model.keras",safe_mode=False,compile=False);print("LOADED",m.input_shape,m.output_shape)'],capture_output=True,text=True,timeout=120)
print('SUBPROCESS_EXIT',r.returncode,'OUT',r.stdout[-500:],'ERR',r.stderr[-1000:],flush=True)
