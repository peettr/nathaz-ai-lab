import pathlib,os
r=pathlib.Path('/content/t8_out');p=r/'host.ack';pair=os.environ['T8_PAIR']
if p.exists():assert p.read_text().strip()==pair
else:p.open('x').write(pair+'\n')
print('ACK',pair)
