from earth2studio.lexicon.hrrr import HRRRFXLexicon
x=HRRRFXLexicon.VOCAB
for k,v in x.items():
 if 'surface' in v and any(s in v for s in ('HGT','Geopotential','TOPO','OROG')):print(k,v)
print('KEYS',list(x)[-50:])
