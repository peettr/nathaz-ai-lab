import hashlib,pathlib
p=pathlib.Path('/content/diagnostic_extract.py')
print('DIAGNOSTIC_SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
