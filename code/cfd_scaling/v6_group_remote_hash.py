import hashlib, os
p='/content/v6_work/group/model_selected_val_r2.pt'
h=hashlib.sha256()
with open(p,'rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):
        h.update(b)
print('V6_GROUP_MODEL_SIZE',os.path.getsize(p))
print('V6_GROUP_MODEL_SHA256',h.hexdigest())
