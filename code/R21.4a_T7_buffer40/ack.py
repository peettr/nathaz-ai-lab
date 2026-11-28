import pathlib,os,hashlib
r=pathlib.Path('/content/t7_out');label=os.environ['T7_ACK_LABEL'];assert label in ('E_s101_off','E_s102_off')
expected=os.environ['T7_ACK_PAIR'];assert len(expected.split())==2
for ext,h in zip(('thin.npz','points80.json'),expected.split()):
 assert (r/f'{label}_{ext}.sha256').read_text().strip()==h
assert (r/f'{label}_points80.json').is_file() and (r/f'{label}_thin.npz').is_file()
p=r/f'{label}.ack'
if p.exists():assert p.read_text().strip()==expected
else:p.open('x').write(expected+'\n')
print('ACK',label,flush=True)
