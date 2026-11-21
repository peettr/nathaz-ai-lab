import urllib.request,hashlib,zipfile,os,subprocess
v='v1.75.2';name=f'rclone-{v}-linux-amd64.zip';url=f'https://downloads.rclone.org/{v}/'
fn='/content/'+name
urllib.request.urlretrieve(url+name,fn)
sums=urllib.request.urlopen('https://downloads.rclone.org/'+v+'/SHA256SUMS').read().decode()
expected=next(x.split()[0] for x in sums.splitlines() if x.endswith(name))
actual=hashlib.sha256(open(fn,'rb').read()).hexdigest()
assert expected==actual,(expected,actual)
with zipfile.ZipFile(fn) as z:
 member=next(x for x in z.namelist() if x.endswith('/rclone'))
 with z.open(member) as src,open('/usr/local/bin/rclone','wb') as dst:
  import shutil;shutil.copyfileobj(src,dst)
os.chmod('/usr/local/bin/rclone',0o755)
print('verified',name,actual,subprocess.check_output(['rclone','version'],text=True).splitlines()[0])
