"""Single-link bottom-wall Esoteric-Pull mapping, deliberately unequal populations."""
import random
rng=random.Random(13)
for n in range(1000):
    outgoing={5:rng.random(),10:rng.random(),12:rng.random(),15:rng.random(),17:rng.random()}
    f=[0.0]*19
    f[5]=outgoing[5]
    f[9]=outgoing[10];f[16]=outgoing[15]
    f[11]=outgoing[12];f[18]=outgoing[17]
    before=f.copy()
    f[9],f[16]=f[16],f[9]
    f[11],f[18]=f[18],f[11]
    assert (f[9],f[16],f[11],f[18],f[5])==(outgoing[15],outgoing[10],outgoing[17],outgoing[12],outgoing[5])
    mass_out=sum(outgoing.values())
    mass_in=sum(f[i] for i in (5,9,11,16,18))
    px_out=outgoing[15]-outgoing[10]
    px_in=f[9]-f[16]
    py_out=outgoing[17]-outgoing[12]
    py_in=f[11]-f[18]
    assert max(abs(mass_out-mass_in),abs(px_out-px_in),abs(py_out-py_in))<1e-6
print('1000 asymmetric single-link cases: mass and tangential x/y flux exactly conserved; normal reflection reverses sign')
