import os
print(os.listdir('/content'))
p='/content/lhigh_fix_regression'
print(open(p+'/progress.log').read()[-2000:] if os.path.exists(p+'/progress.log') else 'not started')
print('done',os.path.exists(p+'/complete.txt'),'error',open(p+'/error.txt').read()[-1000:] if os.path.exists(p+'/error.txt') else '')
