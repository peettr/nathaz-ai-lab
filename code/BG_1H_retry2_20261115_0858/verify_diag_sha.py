import hashlib
p='/content/diagnostic_extract.py'
print('DIAG_SHA256',hashlib.sha256(open(p,'rb').read()).hexdigest())
