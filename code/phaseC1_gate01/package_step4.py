# Package the completed eight small channel profiles for transfer.
import glob,zipfile
with zipfile.ZipFile('/content/step4_results.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in glob.glob('/content/z*_q*_nu*.csv')+glob.glob('/content/z*_q*_nu*.log')+['/content/step4_build.log']:
  z.write(p,p.split('/')[-1])
print('/content/step4_results.zip')
