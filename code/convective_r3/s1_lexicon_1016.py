from earth2studio.lexicon.hrrr import HRRRFXLexicon
x=HRRRFXLexicon.VOCAB;print('LEN',len(x));print('HL',[(k,v) for k,v in x.items() if 'hl' in k][:60]);print('HGT',[(k,v) for k,v in x.items() if 'hgt' in k.lower() or 'orog' in k.lower()][:20]);print('FG',[(k,v) for k,v in x.items() if 'fg10m' in k])
