import pathlib,hashlib,json,os
r=pathlib.Path('/content/t3_run3_out');case=os.environ['T3_CASE'];sha=os.environ['T3_SHA']
assert case in ('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102')
p=r/f'{case}_thin.npz';assert p.is_file()
h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(1048576),b''):h.update(b)
assert h.hexdigest()==sha==(r/f'{case}_thin.sha256').read_text().strip()
with (r/f'{case}_verified.ack').open('x') as f:f.write(sha+'\n')
print('ACK',case,sha)
