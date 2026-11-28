import subprocess
cmd = '''set -euo pipefail
V=v1.75.2
cd /content/l2631/d2_text/full_v2
curl -fsSLO https://downloads.rclone.org/$V/rclone-$V-linux-amd64.zip
curl -fsSL https://downloads.rclone.org/$V/SHA256SUMS | grep "rclone-$V-linux-amd64.zip" | sha256sum -c -
unzip -oq rclone-$V-linux-amd64.zip
install -m 755 rclone-$V-linux-amd64/rclone /usr/local/bin/rclone
rclone version
'''
p = subprocess.run(['bash','-c',cmd],capture_output=True,text=True)
print(p.stdout[-1500:]); print(p.stderr[-1000:]); print('INSTALL_RC',p.returncode)
assert p.returncode==0
