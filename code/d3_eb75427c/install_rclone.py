"""Install official rclone binary in disposable Colab VM after SHA256 verification."""
import subprocess
cmd='''set -euo pipefail
V=v1.75.2
cd /content/l2631/d3
curl -fsSLO https://downloads.rclone.org/$V/rclone-$V-linux-amd64.zip
curl -fsSL https://downloads.rclone.org/$V/SHA256SUMS | grep "rclone-$V-linux-amd64.zip" | sha256sum -c -
unzip -oq rclone-$V-linux-amd64.zip
install -m 755 rclone-$V-linux-amd64/rclone /usr/local/bin/rclone
rclone version
'''
p=subprocess.run(['bash','-c',cmd],capture_output=True,text=True)
print(p.stdout[-1000:],p.stderr[-1000:],'RC',p.returncode,flush=True)
assert p.returncode==0
