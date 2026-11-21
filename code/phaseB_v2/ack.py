import pathlib,os
r=pathlib.Path('/content/phaseb_out');k=os.environ['ACK_LABEL'];v=os.environ['ACK_SHA']
p=r/(k+'_thin.sha256');assert p.read_text().strip()==v
q=r/(k+'.ack')
if q.exists():assert q.read_text().strip()==v
else:q.write_text(v)
print('ACK',k)
