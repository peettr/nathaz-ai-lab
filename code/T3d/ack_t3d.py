import pathlib,hashlib,json,os
r=pathlib.Path('/content/t3_t3d_out');case=os.environ['T3_CASE'];sha=os.environ['T3_SHA']
assert case in ('dx1p0_s107','dx0p5_s107','dx1p0_s108','dx0p5_s108','dx1p0_s109','dx0p5_s109')
p=r/f'{case}_thin.npz';assert p.is_file()
h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(1068576),b''):h.update(b)
assert h.hexdigest()==sha==(r/f'{case}_thin.sha256').read_text().strip()
with (r/f'{case}_verified.ack').open('x') as f:f.write(sha+'\n')
print('ACK',case,sha)
