#!/usr/bin/env python3
"""Check English quoted spans against local PDF text on cited physical pages."""
import csv, re, subprocess, pathlib, unicodedata
ROOT = pathlib.Path(__file__).parent
IDX = list(csv.DictReader(open(ROOT.parent / 'archive_index/kareem_archive_index.csv', encoding='utf-8')))
extra = {'KRM-0198':'./.hermes/profiles/researchos-literature/Kareem12_PDF_Staging/06_PeakFactors.pdf'}
checks = {
 '阵风锋因子.md': [('KRM-0086',2,'the stationary wind model typically used in boundary layer winds may not be valid for gust-front winds'),('KRM-0086',6,'The GG−F can be best captured in terms of four underlying factors'),('KRM-0086',5,'the models utilized in this section are for the sake of establishing an analysis framework'),('KRM-0098',9,'background peak factor in gust-front winds is still unknown due to lack of information regarding the characteristics of gust-front winds')],
 '非高斯峰值因子.md':[('KRM-0046',7,'Gaussian distribution significantly underestimates the tail values.'),('KRM-0198',4,'the reliability of extreme value estimates depends on the level to which the given data set encapsulates the statistical features of the underlying non-Gaussian process, e.g., ergodicity.'),('KRM-0198',2,'the crossings over a level are assumed to be independent of one another.'),('KRM-0198',4,'For non-Gaussian processes, however, this variability is rather large owing to either a positive or negative tail.'),('KRM-0046',4,'the Gram-Charlier series distribution has inherent limitations in defining the tail regions.')],
 '非平稳时变均值与平均时距.md':[('KRM-0107',1,'the question remains as to whether the user-defined interval is appropriate for nonstationary winds.'),('KRM-0107',4,'a VAI approach determines requisite averaging blocks (windows) based specifically on the measured nonstationary wind data.'),('KRM-0107',18,'the traditional FAI scheme is not effective for characterizing the gust factor in a nonstationary event with rapid changes in wind speed.'),('KRM-0107',19,'More full-scale data with higher sampling rates, especially thunderstorm/downburst data, may be necessary to enhance the effectiveness and robustness of VAI schemes.')]
}
def norm(s):
 s=unicodedata.normalize('NFKC',s).replace('\u00ad','').replace('−','-').replace('–','-').replace('—','-')
 s=re.sub(r'-\s*\n\s*','',s)
 return re.sub(r'\s+',' ',s).strip().lower()
fail=0;total=0
for fn,items in checks.items():
 card=(ROOT/fn).read_text(encoding='utf8')
 for wid,page,quote in items:
  total+=1
  row=next(x for x in IDX if x['work_id']==wid)
  path=extra.get(wid) or row['local_pdf_path'].split(';')[0]
  text=subprocess.run(['pdftotext','-f',str(page),'-l',str(page),'-raw',path,'-'],capture_output=True,text=True).stdout
  ok=norm(quote) in norm(text) and quote in card
  print(('PASS' if ok else 'FAIL'),fn,wid,page,quote[:55])
  fail+=not ok
print(f'{total-fail}/{total} verified, {fail} failed')
raise SystemExit(bool(fail))
