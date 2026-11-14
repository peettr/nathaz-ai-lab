from earth2studio.lexicon.hrrr import HRRRFXLexicon
x=HRRRFXLexicon.VOCAB
for prefix in ('t','q','Z','p'):
 print(prefix,[ (k,x[k]) for k in x if k.startswith(prefix) and 'hl' in k][:5], 'count',sum(k.startswith(prefix) and 'hl' in k for k in x))
print('surface',[(k,v) for k,v in x.items() if 'HGT' in v][:20])
