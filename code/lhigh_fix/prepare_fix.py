from pathlib import Path
import tarfile, io
R=Path(__file__).resolve().parent
old=R.parent/'lhigh/lhigh_dfg_fixture.tar.gz'
new=R/'lhigh_fixed_fixture.tar.gz'
needle='reflected=outgoing/(2.0f*q)+(2.0f*q-1.0f)/(2.0f*q)*ibb_post[off+(ulong)back*19ul+opposite];'
replacement='reflected=outgoing/(2.0f*q)+(2.0f*q-1.0f)/(2.0f*q)*ibb_post[off+(ulong)n*19ul+opposite];'
with tarfile.open(old) as inp, tarfile.open(new,'w:gz') as out:
    hits=0
    for member in inp:
        if member.isfile():
            data=inp.extractfile(member).read()
            if member.name.endswith('/src/kernel.cpp'):
                text=data.decode(); assert text.count(needle)==1
                data=text.replace(needle,replacement).encode();hits+=1
            member.size=len(data);out.addfile(member,io.BytesIO(data))
        else:out.addfile(member)
assert hits==1
print(new,new.stat().st_size)
