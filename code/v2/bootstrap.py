from pathlib import Path
import zipfile,subprocess,sys,requests,tarfile,io,os
r=Path('/content/e_terrain_v2');r.mkdir(exist_ok=True)
with zipfile.ZipFile(r/'obs.zip') as z:z.extractall(r)
subprocess.run([sys.executable,'-m','pip','-q','install','fsspec','h5py','eccodes','rasterio','pyproj'],check=True)
subprocess.run(['apt-get','update','-qq'],stdout=subprocess.DEVNULL,check=True)
subprocess.run(['apt-get','install','-y','-qq','gdal-bin'],stdout=subprocess.DEVNULL,check=True)
b=requests.get('https://micro.mamba.pm/api/micromamba/linux-64/latest',timeout=120);b.raise_for_status()
with tarfile.open(fileobj=io.BytesIO(b.content),mode='r:bz2') as t:
 exe=r/'micromamba';exe.write_bytes(t.extractfile('bin/micromamba').read());exe.chmod(0o755)
p=subprocess.run([str(exe),'create','-y','-p',str(r/'wn_env'),'-c','conda-forge','windninja'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1500,env={**os.environ,'MAMBA_ROOT_PREFIX':str(r/'mamba')})
(r/'wn_install.log').write_text(p.stdout);assert p.returncode==0,p.stdout[-1000:]
print('V2_BOOTSTRAP_COMPLETE',flush=True)
