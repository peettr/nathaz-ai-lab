import subprocess,os
print(subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout[-4000:])
p='/content/zenodo19041698/download.log'
print('LOG',open(p).read()[-1000:] if os.path.exists(p) else 'missing')
print('SIZE',os.path.getsize('/content/zenodo19041698/boundaryData.zip') if os.path.exists('/content/zenodo19041698/boundaryData.zip') else 'missing')
