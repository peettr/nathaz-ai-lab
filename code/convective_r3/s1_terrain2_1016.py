from earth2studio.lexicon.hrrr import HRRRFXLexicon,HRRRLexicon
for typ in (HRRRFXLexicon,HRRRLexicon):
 x=typ.VOCAB;print(typ.__name__,len(x));print('orog/hgt surface',[(k,v) for k,v in x.items() if 'surface' in v and ('HGT' in v or 'OROG' in v)]);print('others',[(k,v) for k,v in x.items() if 'orog' in k.lower() or 'terrain' in k.lower() or k.lower() in ('z','zs','hgt','orography')]);
