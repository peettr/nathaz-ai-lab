import pathlib, subprocess
p=pathlib.Path('/content/l2613v3');p.mkdir(exist_ok=True)
(p/'.colab_owner').write_text('L26.13-02 quick researchos-qtl-quick 11-02 v3\n')
assert (p/'coverage.py').exists()
f=(p/'coverage.log').open('xb')
r=subprocess.Popen(['python',str(p/'coverage.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('coverage PID',r.pid,flush=True)
